from __future__ import annotations

from dataclasses import dataclass, field
from collections import defaultdict
from typing import Dict, List, Tuple, Optional, Any, TYPE_CHECKING
import logging
import math

if TYPE_CHECKING:
    from .schemas import (
        BoardLayout,
        CuttingRequest,
        CutSegment,
        EdgingDetail,
        EdgingSummary,
        GrainAlignment,
        OptimizationSummary,
        Options,
        PlacedPanel,
    )

logger = logging.getLogger("panelpro")

EPS = 1e-6


# ───────────────────── Data ─────────────────────
@dataclass(slots=True)
class PanelUnit:
    panel_index: int
    panel: object
    unit_id: int
    width: int
    length: int
    area: int
    label: str


@dataclass
class BoardState:
    board_number: int
    board_width: float
    board_length: float
    placed_panels: list = field(default_factory=list)
    used_area: float = 0.0


# ───────────────────── Helpers ─────────────────────
def _get_schemas():
    """Lazy import to avoid circular imports."""
    from .schemas import (
        BoardLayout,
        CuttingRequest,
        CutSegment,
        EdgingDetail,
        EdgingSummary,
        GrainAlignment,
        OptimizationSummary,
        Options,
        PlacedPanel,
    )
    return {
        "BoardLayout": BoardLayout,
        "CuttingRequest": CuttingRequest,
        "CutSegment": CutSegment,
        "EdgingDetail": EdgingDetail,
        "EdgingSummary": EdgingSummary,
        "GrainAlignment": GrainAlignment,
        "OptimizationSummary": OptimizationSummary,
        "Options": Options,
        "PlacedPanel": PlacedPanel,
    }


def _ensure_request_options(request) -> None:
    from .schemas import Options
    if request.options is None:
        request.options = Options()


def _resolve_board_size(request) -> Tuple[int, int]:
    bw = int(round(float(request.board.width_mm)))
    bl = int(round(float(request.board.length_mm)))
    return bw, bl


def _get_kerf_mm(request) -> int:
    if request.options is not None:
        return int(round(float(request.options.kerf)))
    return 3


def _panel_can_rotate(panel, request) -> bool:
    from .schemas import GrainAlignment
    opts = request.options
    if opts and not opts.allow_rotation:
        return False
    if opts and opts.consider_grain:
        return panel.alignment == GrainAlignment.none
    return True


def _expand_panel_units(request) -> List[PanelUnit]:
    units: List[PanelUnit] = []
    uid = 1
    for idx, p in enumerate(request.panels):
        w = int(round(float(p.width)))
        l = int(round(float(p.length)))
        base_label = p.label or f"Panel-{idx + 1}"
        for i in range(int(p.quantity)):
            units.append(
                PanelUnit(
                    panel_index=idx, panel=p, unit_id=uid,
                    width=w, length=l, area=w * l,
                    label=f"{base_label} #{i + 1}",
                )
            )
            uid += 1
    return units


def _get_orientations(
    unit: PanelUnit, request, bw: int, bl: int
) -> List[Tuple[int, int, bool]]:
    out = []
    if unit.width <= bw and unit.length <= bl:
        out.append((unit.width, unit.length, False))
    if (
        _panel_can_rotate(unit.panel, request)
        and unit.width != unit.length
        and unit.length <= bw
        and unit.width <= bl
    ):
        out.append((unit.length, unit.width, True))
    return out


# ─────────────── Guillotine Recursive Packer ───────────────
@dataclass
class GRect:
    x: int
    y: int
    w: int
    h: int

    @property
    def area(self) -> int:
        return self.w * self.h


def _guillotine_best_fit(
    rect: GRect,
    remaining: List[PanelUnit],
    request, bw: int, bl: int, kerf: int,
) -> Optional[Tuple[int, int, int, bool]]:
    best_idx = -1
    best_w = best_h = 0
    best_rot = False
    best_waste = 999999999999

    for i, unit in enumerate(remaining):
        for pw, ph, rot in _get_orientations(unit, request, bw, bl):
            if pw <= rect.w and ph <= rect.h:
                waste = rect.area - (pw * ph)
                if waste < best_waste or (
                    waste == best_waste and pw * ph > best_w * best_h
                ):
                    best_waste = waste
                    best_idx = i
                    best_w = pw
                    best_h = ph
                    best_rot = rot

    return (best_idx, best_w, best_h, best_rot) if best_idx >= 0 else None


def _guillotine_pack_rect(
    rect: GRect,
    remaining: List[PanelUnit],
    request, bw: int, bl: int, kerf: int,
    placements: List[Tuple[PanelUnit, int, int, int, int, bool]],
) -> None:
    if not remaining or rect.w <= 0 or rect.h <= 0:
        return

    min_w = min(min(u.width, u.length) for u in remaining)
    if rect.w < min_w and rect.h < min_w:
        return

    result = _guillotine_best_fit(rect, remaining, request, bw, bl, kerf)
    if result is None:
        return

    idx, pw, ph, rotated = result
    unit = remaining.pop(idx)
    placements.append((unit, rect.x, rect.y, pw, ph, rotated))

    right_w = rect.w - pw - kerf
    bottom_h = rect.h - ph - kerf
    if right_w < 0:
        right_w = rect.w - pw
    if bottom_h < 0:
        bottom_h = rect.h - ph

    if right_w <= 0 and bottom_h <= 0:
        return

    if right_w > 0 and bottom_h > 0:
        a_right = GRect(rect.x + pw + kerf, rect.y, max(0, right_w), ph)
        a_bottom = GRect(rect.x, rect.y + ph + kerf, rect.w, max(0, bottom_h))
        a_min = min(a_right.area, a_bottom.area)

        b_right = GRect(rect.x + pw + kerf, rect.y, max(0, right_w), rect.h)
        b_bottom = GRect(rect.x, rect.y + ph + kerf, pw, max(0, bottom_h))
        b_min = min(b_right.area, b_bottom.area)

        if a_min >= b_min:
            r1, r2 = a_bottom, a_right
        else:
            r1, r2 = b_right, b_bottom

        if r1.area >= r2.area:
            _guillotine_pack_rect(r1, remaining, request, bw, bl, kerf, placements)
            _guillotine_pack_rect(r2, remaining, request, bw, bl, kerf, placements)
        else:
            _guillotine_pack_rect(r2, remaining, request, bw, bl, kerf, placements)
            _guillotine_pack_rect(r1, remaining, request, bw, bl, kerf, placements)
    elif right_w > 0:
        _guillotine_pack_rect(
            GRect(rect.x + pw + kerf, rect.y, right_w, rect.h),
            remaining, request, bw, bl, kerf, placements,
        )
    elif bottom_h > 0:
        _guillotine_pack_rect(
            GRect(rect.x, rect.y + ph + kerf, rect.w, bottom_h),
            remaining, request, bw, bl, kerf, placements,
        )


def _guillotine_full_pack(
    request, units: List[PanelUnit],
    bw: int, bl: int, kerf: int, sort_key,
) -> Tuple[List[BoardState], List[PanelUnit]]:
    from .schemas import PlacedPanel

    remaining = sorted(list(units), key=sort_key)
    boards: List[BoardState] = []

    while remaining:
        placements: List[Tuple[PanelUnit, int, int, int, int, bool]] = []
        before = len(remaining)

        _guillotine_pack_rect(
            GRect(0, 0, bw, bl), remaining, request, bw, bl, kerf, placements
        )

        if not placements:
            break

        board = BoardState(
            board_number=len(boards) + 1,
            board_width=float(bw), board_length=float(bl),
        )
        for unit, x, y, pw, ph, rotated in placements:
            board.placed_panels.append(PlacedPanel(
                panel_index=unit.panel_index,
                x=float(x), y=float(y),
                width=float(pw), length=float(ph),
                label=unit.label, rotated=rotated,
                grain_aligned=unit.panel.alignment,
                board_number=board.board_number,
            ))
            board.used_area += pw * ph
        boards.append(board)

        if len(remaining) == before:
            break

    return boards, remaining


# ─────────────── MaxRects Bin ───────────────
class MaxRectsBin:
    __slots__ = ("width", "height", "kerf", "free_rects", "used_area")

    def __init__(self, w: int, h: int, kerf: int = 0):
        self.width = w
        self.height = h
        self.kerf = kerf
        self.free_rects: List[List[int]] = [[0, 0, w, h]]
        self.used_area: int = 0

    def find_best(self, pw: int, ph: int, method: int = 0) -> Optional[Tuple[int, int, int, int]]:
        best_x = best_y = -1
        best_s1 = best_s2 = 999999999

        for r in self.free_rects:
            rx, ry, rw, rh = r
            if pw > rw or ph > rh:
                continue
            if method == 0:
                s1 = min(rw - pw, rh - ph)
                s2 = max(rw - pw, rh - ph)
            else:
                s1 = ry
                s2 = rx
            if s1 < best_s1 or (s1 == best_s1 and s2 < best_s2):
                best_s1, best_s2 = s1, s2
                best_x, best_y = rx, ry

        return (best_x, best_y, best_s1, best_s2) if best_x >= 0 else None

    def place(self, px: int, py: int, pw: int, ph: int) -> None:
        self.used_area += pw * ph
        k = self.kerf
        ow = pw + k if px + pw + k <= self.width else pw
        oh = ph + k if py + ph + k <= self.height else ph

        new_rects = []
        i = 0
        while i < len(self.free_rects):
            r = self.free_rects[i]
            rx, ry, rw, rh = r
            if px >= rx + rw or px + ow <= rx or py >= ry + rh or py + oh <= ry:
                i += 1
                continue
            self.free_rects.pop(i)
            if px > rx:
                new_rects.append([rx, ry, px - rx, rh])
            if px + ow < rx + rw:
                new_rects.append([px + ow, ry, rx + rw - px - ow, rh])
            if py > ry:
                new_rects.append([rx, ry, rw, py - ry])
            if py + oh < ry + rh:
                new_rects.append([rx, py + oh, rw, ry + rh - py - oh])

        self.free_rects.extend(new_rects)
        self._prune()

    def _prune(self) -> None:
        n = len(self.free_rects)
        if n <= 1:
            return
        remove = set()
        for i in range(n):
            if i in remove:
                continue
            ri = self.free_rects[i]
            if ri[2] <= 0 or ri[3] <= 0:
                remove.add(i)
                continue
            for j in range(n):
                if i == j or j in remove:
                    continue
                rj = self.free_rects[j]
                if (ri[0] >= rj[0] and ri[1] >= rj[1]
                    and ri[0] + ri[2] <= rj[0] + rj[2]
                    and ri[1] + ri[3] <= rj[1] + rj[3]):
                    remove.add(i)
                    break
        if remove:
            self.free_rects = [self.free_rects[i] for i in range(n) if i not in remove]


def _maxrects_pack(
    request, units: List[PanelUnit],
    bw: int, bl: int, kerf: int,
    sort_key, method: int,
) -> Tuple[List[BoardState], List[PanelUnit]]:
    from .schemas import PlacedPanel

    sorted_units = sorted(units, key=sort_key)
    bins: List[MaxRectsBin] = []
    boards: List[BoardState] = []
    impossible: List[PanelUnit] = []

    for unit in sorted_units:
        orientations = _get_orientations(unit, request, bw, bl)
        if not orientations:
            impossible.append(unit)
            continue

        placed = False
        best_bin = -1
        best_x = best_y = best_pw = best_ph = 0
        best_rot = False
        best_score = (999999999, 999999999)

        for b_idx, b in enumerate(bins):
            for pw, ph, rot in orientations:
                r = b.find_best(pw, ph, method)
                if r and (r[2], r[3]) < best_score:
                    best_score = (r[2], r[3])
                    best_bin = b_idx
                    best_x, best_y = r[0], r[1]
                    best_pw, best_ph, best_rot = pw, ph, rot
                    placed = True

        if placed:
            bins[best_bin].place(best_x, best_y, best_pw, best_ph)
            boards[best_bin].placed_panels.append(PlacedPanel(
                panel_index=unit.panel_index,
                x=float(best_x), y=float(best_y),
                width=float(best_pw), length=float(best_ph),
                label=unit.label, rotated=best_rot,
                grain_aligned=unit.panel.alignment,
                board_number=boards[best_bin].board_number,
            ))
            boards[best_bin].used_area += best_pw * best_ph
        else:
            nb = MaxRectsBin(bw, bl, kerf)
            best_s = (999999999, 999999999)
            bx = by = bpw = bph = 0
            brot = False
            found = False

            for pw, ph, rot in orientations:
                r = nb.find_best(pw, ph, method)
                if r and (r[2], r[3]) < best_s:
                    best_s = (r[2], r[3])
                    bx, by, bpw, bph, brot = r[0], r[1], pw, ph, rot
                    found = True

            if found:
                nb.place(bx, by, bpw, bph)
                bins.append(nb)
                board = BoardState(
                    board_number=len(boards) + 1,
                    board_width=float(bw), board_length=float(bl),
                )
                board.placed_panels.append(PlacedPanel(
                    panel_index=unit.panel_index,
                    x=float(bx), y=float(by),
                    width=float(bpw), length=float(bph),
                    label=unit.label, rotated=brot,
                    grain_aligned=unit.panel.alignment,
                    board_number=board.board_number,
                ))
                board.used_area += bpw * bph
                boards.append(board)
            else:
                impossible.append(unit)

    return boards, impossible


# ─────────────── Hybrid Guillotine + Gap Fill ───────────────
def _hybrid_guillotine_pack(
    request, units: List[PanelUnit],
    bw: int, bl: int, kerf: int, sort_key,
) -> Tuple[List[BoardState], List[PanelUnit]]:
    from .schemas import PlacedPanel

    boards, remaining = _guillotine_full_pack(request, units, bw, bl, kerf, sort_key)

    if not remaining:
        return boards, []

    still_remaining = list(remaining)
    for board in boards:
        if not still_remaining:
            break

        filler = MaxRectsBin(bw, bl, kerf)
        for p in board.placed_panels:
            filler.place(int(p.x), int(p.y), int(p.width), int(p.length))
            filler.used_area -= int(p.width) * int(p.length)
        filler.used_area = 0

        new_remaining = []
        for unit in still_remaining:
            orientations = _get_orientations(unit, request, bw, bl)
            placed = False
            best_r = None
            best_pw = best_ph = 0
            best_rot = False
            best_s = (999999999, 999999999)

            for pw, ph, rot in orientations:
                r = filler.find_best(pw, ph, 0)
                if r and (r[2], r[3]) < best_s:
                    best_s = (r[2], r[3])
                    best_r = r
                    best_pw, best_ph, best_rot = pw, ph, rot
                    placed = True

            if placed and best_r:
                filler.place(best_r[0], best_r[1], best_pw, best_ph)
                board.placed_panels.append(PlacedPanel(
                    panel_index=unit.panel_index,
                    x=float(best_r[0]), y=float(best_r[1]),
                    width=float(best_pw), length=float(best_ph),
                    label=unit.label, rotated=best_rot,
                    grain_aligned=unit.panel.alignment,
                    board_number=board.board_number,
                ))
                board.used_area += best_pw * best_ph
            else:
                new_remaining.append(unit)
        still_remaining = new_remaining

    if still_remaining:
        extra, still_remaining = _guillotine_full_pack(
            request, still_remaining, bw, bl, kerf, sort_key
        )
        for eb in extra:
            eb.board_number = len(boards) + 1
            for p in eb.placed_panels:
                p.board_number = eb.board_number
            boards.append(eb)

    return boards, still_remaining


# ─────────────── Strategy Runner ───────────────
def _run_all_strategies(
    request, units: List[PanelUnit],
    bw: int, bl: int, kerf: int,
) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    sort_keys = {
        "area": lambda u: (-u.area, -max(u.width, u.length)),
        "maxdim": lambda u: (-max(u.width, u.length), -u.area),
        "perim": lambda u: (-(2 * u.width + 2 * u.length), -u.area),
        "width": lambda u: (-u.width, -u.length, -u.area),
        "length": lambda u: (-u.length, -u.width, -u.area),
    }

    best_boards: Optional[List[BoardState]] = None
    best_imp: List[PanelUnit] = list(units)
    best_key = None
    best_name = ""
    board_area = bw * bl

    def evaluate(name: str, boards: List[BoardState], imp: List[PanelUnit]):
        nonlocal best_boards, best_imp, best_key, best_name
        if not boards and imp:
            return
        total_used = sum(b.used_area for b in boards)
        n_boards = max(1, len(boards))
        waste = n_boards * board_area - total_used
        key = (len(imp), len(boards), waste, -total_used)
        eff = total_used / (n_boards * board_area) * 100 if boards else 0
        logger.info(f"  {name}: {len(boards)} boards, eff={eff:.1f}%")

        if best_key is None or key < best_key:
            best_key = key
            best_boards = boards
            best_imp = imp
            best_name = name

    for sn, sf in sort_keys.items():
        try:
            b, i = _hybrid_guillotine_pack(request, units, bw, bl, kerf, sf)
            evaluate(f"Guil-{sn}", b, i)
        except Exception as e:
            logger.warning(f"Guil-{sn} failed: {e}")

    for sn, sf in sort_keys.items():
        for m in [0, 1]:
            try:
                b, i = _maxrects_pack(request, units, bw, bl, kerf, sf, m)
                mn = "BSSF" if m == 0 else "BL"
                evaluate(f"MR-{sn}-{mn}", b, i)
            except Exception as e:
                logger.warning(f"MR-{sn}-{m} failed: {e}")

    return best_boards or [], best_imp, [f"Best: {best_name}"]


# ─────────────── Validation ───────────────
def _validate_boards(boards: List[BoardState], bw: float, bl: float) -> None:
    for b in boards:
        for i in range(len(b.placed_panels)):
            pi = b.placed_panels[i]
            if pi.x < -EPS or pi.y < -EPS:
                logger.warning(f"Negative pos: {pi.label}")
            if pi.x + pi.width > bw + EPS:
                logger.warning(f"{pi.label} exceeds width")
            if pi.y + pi.length > bl + EPS:
                logger.warning(f"{pi.label} exceeds length")
            for j in range(i + 1, len(b.placed_panels)):
                pj = b.placed_panels[j]
                if not (
                    pi.x + pi.width <= pj.x + EPS
                    or pj.x + pj.width <= pi.x + EPS
                    or pi.y + pi.length <= pj.y + EPS
                    or pj.y + pj.length <= pi.y + EPS
                ):
                    logger.error(
                        f"Overlap board {b.board_number}: {pi.label} & {pj.label}"
                    )


# ─────────────── Cuts ───────────────
def _generate_cuts(board: BoardState, kerf: int) -> list:
    from .schemas import CutSegment

    cuts = []
    cid = 1
    xs, ys = set(), set()

    for p in board.placed_panels:
        xc = p.x + p.width + (kerf / 2.0 if kerf > 0 else 0.0)
        yc = p.y + p.length + (kerf / 2.0 if kerf > 0 else 0.0)
        if xc < board.board_width - EPS:
            xs.add(round(xc, 4))
        if yc < board.board_length - EPS:
            ys.add(round(yc, 4))

    for x in sorted(xs):
        cuts.append(CutSegment(
            id=cid, orientation="vertical", direction="vertical",
            x1=float(x), y1=0.0, x2=float(x), y2=float(board.board_length),
            length=float(board.board_length), label=f"Rip at x={x:.1f}",
        ))
        cid += 1
    for y in sorted(ys):
        cuts.append(CutSegment(
            id=cid, orientation="horizontal", direction="horizontal",
            x1=0.0, y1=float(y), x2=float(board.board_width), y2=float(y),
            length=float(board.board_width), label=f"Cross at y={y:.1f}",
        ))
        cid += 1
    return cuts


# ─────────────── Edging ───────────────
def _build_edging(request) -> Any:
    from .schemas import EdgingSummary, EdgingDetail

    total_m = 0.0
    details = []
    for p in request.panels:
        epm = p.edge_length_mm / 1000.0
        tem = p.total_edge_length_mm / 1000.0
        total_m += tem
        ea = "".join(
            s[0].upper() for s, f in [
                ("top", p.edging.top), ("right", p.edging.right),
                ("bottom", p.edging.bottom), ("left", p.edging.left),
            ] if f
        ) or "None"
        details.append(EdgingDetail(
            panel_label=p.label or "Panel",
            quantity=int(p.quantity),
            edge_per_panel_m=epm,
            total_edge_m=tem,
            edges_applied=ea,
        ))
    return EdgingSummary(total_meters=total_m, details=details)


# ─────────────── Summary ───────────────
def _build_summary(
    request, boards, total_used, imp_labels, warnings,
    kerf_mm, bw, bl, total_panels, total_edging_m,
):
    from .schemas import OptimizationSummary, GrainAlignment

    ba = bw * bl
    tw = sum(b.waste_area_mm2 for b in boards)
    tba = ba * max(len(boards), 1)
    grain = any(p.alignment != GrainAlignment.none for p in request.panels)

    return OptimizationSummary(
        total_boards=len(boards),
        total_panels=total_panels,
        unique_panel_types=len(request.panels),
        total_edging_meters=total_edging_m,
        total_cuts=sum(len(b.cuts) for b in boards),
        total_cut_length=sum(c.length for b in boards for c in b.cuts),
        total_waste_mm2=tw,
        total_waste_percent=tw / tba * 100 if tba > 0 else 0,
        board_width=bw,
        board_length=bl,
        total_used_area_mm2=total_used,
        overall_efficiency_percent=total_used / tba * 100 if tba > 0 else 0,
        kerf_mm=kerf_mm,
        grain_considered=grain,
        material_groups=1,
        impossible_panels=imp_labels,
        warnings=warnings,
    )


# ─────────────── Layout Builder ───────────────
def _work_to_layouts(
    request, boards_work: List[BoardState],
    impossible_units: List[PanelUnit],
    warnings: Optional[List[str]] = None,
) -> Tuple:
    from .schemas import BoardLayout, EdgingSummary

    bw, bl = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)
    warnings = warnings or []
    boards_work = [b for b in boards_work if b.used_area > EPS]

    _validate_boards(boards_work, float(bw), float(bl))

    boards = []
    total_used = 0.0
    ba = float(bw * bl)

    material_info = {
        "board_type": request.board.board_type,
        "thickness_mm": request.board.thickness_mm,
        "company": request.board.company,
        "color_name": request.board.color_name,
    }

    for b in boards_work:
        b.placed_panels.sort(key=lambda p: (p.y, p.x))
        used = float(b.used_area)
        waste = max(ba - used, 0.0)
        eff = used / ba * 100 if ba > 0 else 0
        total_used += used

        gen_cuts = request.options and request.options.generate_cuts
        cuts = _generate_cuts(b, kerf) if gen_cuts else []

        boards.append(BoardLayout(
            board_number=b.board_number,
            board_width=float(bw),
            board_length=float(bl),
            used_area_mm2=used,
            waste_area_mm2=waste,
            efficiency_percent=eff,
            panel_count=len(b.placed_panels),
            source=f"{request.board.company} {request.board.color_name}",
            material=material_info,
            panels=b.placed_panels,
            cuts=cuts,
        ))

    edging = _build_edging(request)
    summary = _build_summary(
        request, boards, total_used,
        [u.label for u in impossible_units],
        warnings,
        float(kerf), float(bw), float(bl),
        sum(int(p.quantity) for p in request.panels),
        edging.total_meters,
    )
    return boards, summary, edging


# ─────────────── MAIN ENTRY ───────────────
def run_optimization(request) -> Tuple:
    _ensure_request_options(request)
    bw, bl = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)

    logger.info(
        f"Optimizer: board={bw}x{bl} kerf={kerf} "
        f"material={request.board.company} {request.board.color_name}"
    )

    units = _expand_panel_units(request)

    feasible, impossible_pre = [], []
    for u in units:
        if _get_orientations(u, request, bw, bl):
            feasible.append(u)
        else:
            impossible_pre.append(u)

    if not feasible:
        return _work_to_layouts(request, [], impossible_pre, ["No panels fit the board."])

    total_area = sum(u.area for u in feasible)
    board_area = bw * bl
    logger.info(
        f"Panels: {len(feasible)}, area: {total_area}, "
        f"min boards: {math.ceil(total_area / board_area)}"
    )

    boards, imp, warnings = _run_all_strategies(request, feasible, bw, bl, kerf)

    all_imp = impossible_pre + imp
    return _work_to_layouts(request, boards, all_imp, warnings)
