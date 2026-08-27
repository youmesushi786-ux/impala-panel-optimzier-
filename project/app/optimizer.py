from __future__ import annotations

import os
import math
import logging
from uuid import uuid4
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from app.schemas import (
    BoardLayout, CuttingRequest, CutSegment, EdgingDetail, EdgingSummary,
    GrainAlignment, OptimizationSummary, Options, PlacedPanel,
    OffcutUsedItem, OffcutCreatedItem, StickerLabel
)
from app.config import PUBLIC_BASE_URL

logger = logging.getLogger("panelpro")
EPS = 1e-6


@dataclass(slots=True)
class PanelUnit:
    panel_index: int
    panel: object
    unit_id: int
    width: float
    length: float
    area: float
    label: str


@dataclass
class BoardState:
    board_number: int
    board_width: float
    board_length: float
    placed_panels: List[PlacedPanel] = field(default_factory=list)
    used_area: float = 0.0
    is_offcut: bool = False
    offcut_id: Optional[int] = None
    offcut_code: Optional[str] = None
    remnant_width: float = 0.0
    remnant_length: float = 0.0


def _ensure_request_options(request: CuttingRequest) -> None:
    if request.options is None:
        request.options = Options()


def _resolve_board_size(request: CuttingRequest) -> Tuple[float, float]:
    bw = float(getattr(request.board, "width_mm", None) or 1220.0)
    bl = float(getattr(request.board, "length_mm", None) or 2440.0)
    trim = float(getattr(request.options, "trim_margin_mm", 0.0))
    return max(1.0, bw - 2.0 * trim), max(1.0, bl - 2.0 * trim)


def _get_kerf_mm(request: CuttingRequest) -> float:
    return float(getattr(request.options, "kerf", 3.0))


def _get_edge_thickness_mm(request: CuttingRequest) -> float:
    if not request.options or not getattr(request.options, "edge_banding", True):
        return 0.0
    return float(getattr(request.options, "edge_thickness_mm", 0.0))


def _panel_can_rotate(panel, request: CuttingRequest) -> bool:
    opts = request.options
    if opts and not getattr(opts, "allow_rotation", True): return False
    if opts and not getattr(opts, "consider_grain", False): return True
    return getattr(panel, "alignment", GrainAlignment.none) == GrainAlignment.none


def _expand_panel_units(request: CuttingRequest) -> List[PanelUnit]:
    units, uid = [], 1
    edge_thick = _get_edge_thickness_mm(request)
    for idx, p in enumerate(request.panels):
        w, l = float(p.width), float(p.length)
        if edge_thick > 0 and getattr(p, "edging", None):
            w -= (edge_thick if p.edging.left else 0.0) + (edge_thick if p.edging.right else 0.0)
            l -= (edge_thick if p.edging.top else 0.0) + (edge_thick if p.edging.bottom else 0.0)
        w, l = max(1.0, w), max(1.0, l)
        for i in range(int(p.quantity)):
            units.append(PanelUnit(panel_index=idx, panel=p, unit_id=uid, width=w, length=l, area=w*l, label=f"{p.label or 'Panel'} #{i+1}"))
            uid += 1
    return units


def _get_orientations(unit: PanelUnit, request: CuttingRequest, bw: float, bl: float) -> List[Tuple[float, float, bool]]:
    out = []
    if unit.width <= bw + EPS and unit.length <= bl + EPS: out.append((unit.width, unit.length, False))
    if _panel_can_rotate(unit.panel, request) and abs(unit.width - unit.length) > EPS and unit.length <= bw + EPS and unit.width <= bl + EPS:
        out.append((unit.length, unit.width, True))
    return out


class MaxRectsBin:
    __slots__ = ("width", "height", "kerf", "free_rects", "used_area")
    def __init__(self, w: float, h: float, kerf: float):
        self.width, self.height, self.kerf = w, h, kerf
        self.free_rects, self.used_area = [[0.0, 0.0, w, h]], 0.0

    def find_best(self, pw: float, ph: float, method: int = 0):
        best_x = best_y = -1.0
        best_s1 = best_s2 = math.inf
        for rx, ry, rw, rh in self.free_rects:
            if pw > rw + EPS or ph > rh + EPS: continue
            if method == 0: s1, s2 = min(rw - pw, rh - ph), max(rw - pw, rh - ph)
            else: s1, s2 = ry + ph, rx
            if s1 < best_s1 - EPS or (abs(s1 - best_s1) < EPS and s2 < best_s2):
                best_s1, best_s2, best_x, best_y = s1, s2, rx, ry
        return (best_x, best_y, best_s1, best_s2) if best_x >= 0 else None

    def place(self, px: float, py: float, pw: float, ph: float):
        self.used_area += pw * ph
        k = self.kerf
        ow = pw + k if px + pw + k <= self.width + EPS else pw
        oh = ph + k if py + ph + k <= self.height + EPS else ph
        new_rects = []
        i = 0
        while i < len(self.free_rects):
            rx, ry, rw, rh = self.free_rects[i]
            if px >= rx + rw - EPS or px + ow <= rx + EPS or py >= ry + rh - EPS or py + oh <= ry + EPS:
                i += 1
                continue
            self.free_rects.pop(i)
            if px > rx + EPS: new_rects.append([rx, ry, px - rx, rh])
            if px + ow < rx + rw - EPS: new_rects.append([px + ow, ry, rx + rw - px - ow, rh])
            if py > ry + EPS: new_rects.append([rx, ry, rw, py - ry])
            if py + oh < ry + rh - EPS: new_rects.append([rx, py + oh, rw, ry + rh - py - oh])
        self.free_rects.extend(new_rects)
        self._prune()

    def _prune(self):
        n = len(self.free_rects)
        if n <= 1: return
        remove = set()
        for i in range(n):
            if i in remove: continue
            ri = self.free_rects[i]
            if ri[2] <= EPS or ri[3] <= EPS:
                remove.add(i)
                continue
            for j in range(n):
                if i == j or j in remove: continue
                rj = self.free_rects[j]
                if (ri[0] >= rj[0] - EPS and ri[1] >= rj[1] - EPS and ri[0] + ri[2] <= rj[0] + rj[2] + EPS and ri[1] + ri[3] <= rj[1] + rj[3] + EPS):
                    remove.add(i)
                    break
        if remove: self.free_rects = [self.free_rects[i] for i in range(n) if i not in remove]


def _maxrects_pack(request, units, bw, bl, kerf, sort_key, method):
    sorted_units = sorted(units, key=sort_key)
    bins, boards, impossible = [], [], []
    for unit in sorted_units:
        orientations = _get_orientations(unit, request, bw, bl)
        if not orientations:
            impossible.append(unit)
            continue
        best_bin, best_x, best_y, best_pw, best_ph, best_rot, best_score = -1, 0.0, 0.0, 0.0, 0.0, False, (math.inf, math.inf)
        for b_idx, b in enumerate(bins):
            for pw, ph, rot in orientations:
                r = b.find_best(pw, ph, method)
                if r and (r[2], r[3]) < best_score:
                    best_score, best_bin, best_x, best_y, best_pw, best_ph, best_rot = (r[2], r[3]), b_idx, r[0], r[1], pw, ph, rot
        if best_bin >= 0:
            bins[best_bin].place(best_x, best_y, best_pw, best_ph)
            boards[best_bin].placed_panels.append(PlacedPanel(panel_index=unit.panel_index, x=best_x, y=best_y, width=best_pw, length=best_ph, footprint_width=best_pw, footprint_length=best_ph, original_width=unit.width, original_length=unit.length, label=unit.label, rotated=best_rot, grain_aligned=unit.panel.alignment, board_number=boards[best_bin].board_number))
            boards[best_bin].used_area += best_pw * best_ph
        else:
            nb = MaxRectsBin(bw, bl, kerf)
            best_s, bx, by, bpw, bph, brot, found = (math.inf, math.inf), 0.0, 0.0, 0.0, 0.0, False, False
            for pw, ph, rot in orientations:
                r = nb.find_best(pw, ph, method)
                if r and (r[2], r[3]) < best_s:
                    best_s, bx, by, bpw, bph, brot, found = (r[2], r[3]), r[0], r[1], pw, ph, rot, True
            if found:
                nb.place(bx, by, bpw, bph)
                bins.append(nb)
                board = BoardState(board_number=len(boards) + 1, board_width=bw, board_length=bl)
                board.placed_panels.append(PlacedPanel(panel_index=unit.panel_index, x=bx, y=by, width=bpw, length=bph, footprint_width=bpw, footprint_length=bph, original_width=unit.width, original_length=unit.length, label=unit.label, rotated=brot, grain_aligned=unit.panel.alignment, board_number=board.board_number))
                board.used_area += bpw * bph
                boards.append(board)
            else:
                impossible.append(unit)
    return boards, impossible


def _run_offcut_phase(request: CuttingRequest, units: List[PanelUnit], kerf: float) -> Tuple[List[BoardState], List[PanelUnit]]:
    if not getattr(request.options, "use_offcuts", True) or not getattr(request, "available_offcuts", []):
        return [], units

    offcuts = sorted(request.available_offcuts, key=lambda o: (o.width_mm * o.length_mm))
    used_boards, remaining_units = [], list(units)
    sort_key = lambda u: (-u.area, -max(u.width, u.length))
    
    for offcut in offcuts:
        if not remaining_units: break
        bw, bl = float(offcut.width_mm), float(offcut.length_mm)
        boards, imp = _maxrects_pack(request, remaining_units, bw, bl, kerf, sort_key, method=0)
        if boards and boards[0].placed_panels:
            b = boards[0]
            b.is_offcut = True
            b.offcut_id = offcut.offcut_id
            b.offcut_code = offcut.offcut_code or f"OFFCUT-{b.offcut_id}"
            b.board_number = len(used_boards) + 1
            for p in b.placed_panels: p.board_number = b.board_number
            used_boards.append(b)
            remaining_units = imp
            
    return used_boards, remaining_units


def _run_full_sheet_phase(request, units, bw, bl, kerf) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    if not units: return [], [], ["All panels fit on offcuts!"]

    sort_keys = {
        "area": lambda u: (-u.area, -max(u.width, u.length)),
        "length": lambda u: (-u.length, -u.width, -u.area),
    }

    best_boards, best_imp, best_key, best_name = None, list(units), None, ""
    board_area = bw * bl

    def evaluate(name: str, boards: List[BoardState], imp: List[PanelUnit]):
        nonlocal best_boards, best_imp, best_key, best_name
        total_used = sum(b.used_area for b in boards)
        n_boards = len(boards)
        
        # Bounding Box Density Scoring: Gap-filling corner packing
        bbox_area = 0.0
        if boards and boards[-1].placed_panels:
            max_x = max((p.x + p.width) for p in boards[-1].placed_panels)
            max_y = max((p.y + p.length) for p in boards[-1].placed_panels)
            bbox_area = max_x * max_y
        
        key = (len(imp), n_boards, -total_used, bbox_area)
        if best_key is None or key < best_key:
            best_key, best_boards, best_imp, best_name = key, boards, imp, name

    for sn, sf in sort_keys.items():
        for m in [0, 1, 2, 3]:
            try: evaluate(f"MaxRects-{sn}-{m}", *_maxrects_pack(request, units, bw, bl, kerf, sf, m))
            except Exception as e: logger.warning(f"MR-{sn}-{m} failed: {e}")

    return best_boards or [], best_imp, [f"Optimized using: {best_name}"]


def _calculate_remnant(board: BoardState) -> Tuple[float, float]:
    if not board.placed_panels: return board.board_width, board.board_length
    max_x = max((p.x + p.width) for p in board.placed_panels)
    max_y = max((p.y + p.length) for p in board.placed_panels)
    
    area_a = (board.board_width - max_x) * board.board_length
    area_b = board.board_width * (board.board_length - max_y)
    
    if area_a > area_b and area_a > 0: return (board.board_width - max_x), board.board_length
    elif area_b > 0: return board.board_width, (board.board_length - max_y)
    return 0.0, 0.0


def _build_outputs(request: CuttingRequest, offcut_boards: List[BoardState], full_boards: List[BoardState], impossible_units: List[PanelUnit], warnings: List[str]):
    all_boards = offcut_boards + full_boards
    for idx, b in enumerate(all_boards, start=1):
        b.board_number = idx
        for p in b.placed_panels: p.board_number = idx

    bw, bl = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)
    layouts, offcuts_used, offcuts_to_create, stickers = [], [], [], []
    total_used, total_waste, total_cuts, total_cut_length = 0.0, 0.0, 0, 0.0

    for b in all_boards:
        b.placed_panels.sort(key=lambda p: (p.y, p.x))
        ba = b.board_width * b.board_length
        used = b.used_area
        waste = max(ba - used, 0.0)
        eff = used / ba * 100 if ba > 0 else 0
        total_used += used
        total_waste += waste

        cuts, cid, xs, ys = [], 1, set(), set()
        if getattr(request.options, "generate_cuts", True):
            for p in b.placed_panels:
                xs.add(round(p.x + p.width + (kerf/2 if kerf>0 else 0), 4))
                ys.add(round(p.y + p.length + (kerf/2 if kerf>0 else 0), 4))
            for x in sorted(xs):
                if x < b.board_width: cuts.append(CutSegment(id=cid, sequence=cid, orientation="vertical", x1=x, y1=0, x2=x, y2=b.board_length, length=b.board_length, label=f"Rip at {x:.1f}")); cid += 1
            for y in sorted(ys):
                if y < b.board_length: cuts.append(CutSegment(id=cid, sequence=cid, orientation="horizontal", x1=0, y1=y, x2=b.board_width, y2=y, length=b.board_width, label=f"Cross at {y:.1f}")); cid += 1
        
        total_cuts += len(cuts)
        total_cut_length += sum(c.length for c in cuts)

        rem_w, rem_l = _calculate_remnant(b)
        b.remnant_width, b.remnant_length = rem_w, rem_l
        
        min_w = getattr(request.options, "min_offcut_width_mm", 300.0)
        min_l = getattr(request.options, "min_offcut_length_mm", 300.0)
        min_area = getattr(request.options, "min_offcut_area_mm2", 90000.0)
        
        if (rem_w >= min_w and rem_l >= min_l) or (rem_w * rem_l >= min_area):
            offcuts_to_create.append(OffcutCreatedItem(
                width_mm=rem_w, length_mm=rem_l, area_mm2=rem_w * rem_l,
                board_type=request.board.board_type, thickness_mm=request.board.thickness_mm,
                color_name=request.board.color_name, company=request.board.company,
                source_board_number=b.board_number, source="waste"
            ))

        source_type = "offcut" if b.is_offcut else "full_sheet"
        if b.is_offcut:
            offcuts_used.append(OffcutUsedItem(
                offcut_id=b.offcut_id, offcut_code=b.offcut_code,
                width_mm=b.board_width, length_mm=b.board_length,
                board_number=b.board_number, used_area_mm2=used, efficiency_percent=eff
            ))

        layouts.append(BoardLayout(
            board_number=b.board_number, board_width=b.board_width, board_length=b.board_length,
            used_area_mm2=used, waste_area_mm2=waste, efficiency_percent=eff,
            panel_count=len(b.placed_panels), source=source_type,
            offcut_id=b.offcut_id, offcut_code=b.offcut_code,
            remnant_width_mm=rem_w, remnant_length_mm=rem_l,
            material={"board_type": request.board.board_type, "color_name": request.board.color_name, "company": request.board.company},
            panels=b.placed_panels, cuts=cuts,
        ))

        for p in b.placed_panels:
            serial = f"STK-{uuid4().hex[:8].upper()}"
            stickers.append(StickerLabel(
                serial_number=serial, panel_label=p.label, width=p.width, length=p.length,
                board_number=b.board_number, x=p.x, y=p.y, rotated=p.rotated,
                project_name=request.project_name, customer_name=request.customer_name,
                board_type=request.board.board_type, thickness_mm=request.board.thickness_mm,
                company=request.board.company, color_name=request.board.color_name,
                notes=p.notes, qr_url=f"{PUBLIC_BASE_URL}/api/tracking/{serial}",
                source=source_type, offcut_code=b.offcut_code
            ))

    total_m, details = 0.0, []
    for p in request.panels:
        epm, tem = p.edge_length_mm / 1000.0, p.total_edge_length_mm / 1000.0
        total_m += tem
        ea = "".join(s[0].upper() for s, f in [("top", p.edging.top), ("right", p.edging.right), ("bottom", p.edging.bottom), ("left", p.edging.left)] if f) or "None"
        details.append(EdgingDetail(panel_label=p.label or "Panel", quantity=p.quantity, edge_per_panel_m=epm, total_edge_m=tem, edges_applied=ea))
    
    tba = total_used + total_waste
    summary = OptimizationSummary(
        total_boards=len(layouts), total_full_sheets=len(full_boards),
        total_offcuts_used=len(offcut_boards), total_offcuts_created=len(offcuts_to_create),
        total_panels=sum(p.quantity for p in request.panels), unique_panel_types=len(request.panels),
        total_edging_meters=total_m, total_cuts=total_cuts, total_cut_length=total_cut_length,
        total_waste_mm2=total_waste, total_waste_percent=total_waste / tba * 100 if tba > 0 else 0,
        board_width=bw, board_length=bl, total_used_area_mm2=total_used,
        overall_efficiency_percent=total_used / tba * 100 if tba > 0 else 0,
        kerf_mm=kerf, grain_considered=any(p.alignment != GrainAlignment.none for p in request.panels),
        impossible_panels=[u.label for u in impossible_units], warnings=warnings,
        offcuts_available_considered=len(getattr(request, "available_offcuts", []))
    )

    return layouts, summary, EdgingSummary(total_meters=total_m, details=details), stickers, offcuts_used, offcuts_to_create


def run_optimization(request: CuttingRequest):
    _ensure_request_options(request)
    bw, bl = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)

    units = _expand_panel_units(request)
    feasible, impossible_pre = [], []

    for u in units:
        if _get_orientations(u, request, bw, bl) or _get_orientations(u, request, max(bw, bl), max(bw, bl)):
            feasible.append(u)
        else: impossible_pre.append(u)

    if not feasible: return _build_outputs(request, [], [], impossible_pre, ["No panels fit."])

    offcut_boards, remaining_units = _run_offcut_phase(request, feasible, kerf)
    full_boards, imp, warnings = _run_full_sheet_phase(request, remaining_units, bw, bl, kerf)
    
    return _build_outputs(request, offcut_boards, full_boards, impossible_pre + imp, warnings)
