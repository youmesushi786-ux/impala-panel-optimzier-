from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import logging

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
    StickerLabel,
)

logger = logging.getLogger("panelpro")

EPS = 1e-6
TRIM_MARGIN_MM = 0.0


@dataclass(slots=True)
class PanelUnit:
    panel_index: int
    panel: object
    unit_id: int
    width: float
    length: float
    area: float
    label: str


@dataclass(slots=True)
class FreeRect:
    x: float
    y: float
    width: float
    length: float


@dataclass
class BoardState:
    board_number: int
    board_width: float
    board_length: float
    placed_panels: List[PlacedPanel] = field(default_factory=list)
    free_rects: List[FreeRect] = field(default_factory=list)
    used_area: float = 0.0

    def __post_init__(self):
        if not self.free_rects:
            self.free_rects = [FreeRect(0.0, 0.0, self.board_width, self.board_length)]


def _ensure_request_options(request: CuttingRequest) -> None:
    if request.options is None:
        request.options = Options()


def _resolve_board_size(request: CuttingRequest) -> Tuple[float, float]:
    return (
        float(request.board.width_mm) - 2.0 * TRIM_MARGIN_MM,
        float(request.board.length_mm) - 2.0 * TRIM_MARGIN_MM,
    )


def _get_kerf_mm(request: CuttingRequest) -> float:
    if request.options is None:
        return 3.0
    return float(request.options.kerf or 3.0)


def _panel_can_rotate(panel, request: CuttingRequest) -> bool:
    allow_rotation = getattr(request.options, "allow_rotation", True) if request.options else True
    consider_grain = getattr(request.options, "consider_grain", False) if request.options else False

    if not allow_rotation:
        return False

    if consider_grain:
        return panel.alignment == GrainAlignment.none

    return True


def _expand_panel_units(request: CuttingRequest) -> List[PanelUnit]:
    units: List[PanelUnit] = []
    uid = 1

    for idx, p in enumerate(request.panels):
        w = float(p.width)
        l = float(p.length)

        for i in range(int(p.quantity)):
            units.append(
                PanelUnit(
                    panel_index=idx,
                    panel=p,
                    unit_id=uid,
                    width=w,
                    length=l,
                    area=w * l,
                    label=p.label or f"Panel-{idx + 1}-{i + 1}",
                )
            )
            uid += 1

    return units


def _candidate_orientations(unit: PanelUnit, request: CuttingRequest) -> List[Tuple[float, float, bool]]:
    out = [(unit.width, unit.length, False)]
    if _panel_can_rotate(unit.panel, request) and abs(unit.width - unit.length) > EPS:
        out.append((unit.length, unit.width, True))
    return out


def _merge_free_rects(rects: List[FreeRect]) -> List[FreeRect]:
    changed = True
    result = rects[:]

    while changed:
        changed = False
        merged: List[FreeRect] = []
        used = [False] * len(result)

        for i in range(len(result)):
            if used[i]:
                continue

            a = result[i]
            merged_rect = a

            for j in range(i + 1, len(result)):
                if used[j]:
                    continue

                b = result[j]

                # vertical merge
                if abs(a.x - b.x) < EPS and abs(a.width - b.width) < EPS:
                    if abs(a.y + a.length - b.y) < EPS:
                        merged_rect = FreeRect(a.x, a.y, a.width, a.length + b.length)
                        used[j] = True
                        changed = True
                        break
                    elif abs(b.y + b.length - a.y) < EPS:
                        merged_rect = FreeRect(b.x, b.y, b.width, b.length + a.length)
                        used[j] = True
                        changed = True
                        break

                # horizontal merge
                if abs(a.y - b.y) < EPS and abs(a.length - b.length) < EPS:
                    if abs(a.x + a.width - b.x) < EPS:
                        merged_rect = FreeRect(a.x, a.y, a.width + b.width, a.length)
                        used[j] = True
                        changed = True
                        break
                    elif abs(b.x + b.width - a.x) < EPS:
                        merged_rect = FreeRect(b.x, b.y, b.width + a.width, b.length)
                        used[j] = True
                        changed = True
                        break

            used[i] = True
            merged.append(merged_rect)

        result = merged

    return result


def _prune_free_rects(rects: List[FreeRect]) -> List[FreeRect]:
    pruned: List[FreeRect] = []

    for i, a in enumerate(rects):
        contained = False
        for j, b in enumerate(rects):
            if i == j:
                continue
            if (
                a.x >= b.x - EPS
                and a.y >= b.y - EPS
                and a.x + a.width <= b.x + b.width + EPS
                and a.y + a.length <= b.y + b.length + EPS
            ):
                contained = True
                break

        if not contained and a.width > EPS and a.length > EPS:
            pruned.append(a)

    return _merge_free_rects(pruned)


def _split_free_rect(free_rect: FreeRect, x: float, y: float, w: float, l: float, kerf: float) -> List[FreeRect]:
    new_rects: List[FreeRect] = []

    placed_right = x + w
    placed_bottom = y + l

    right_x = placed_right + kerf
    bottom_y = placed_bottom + kerf

    # right remainder
    if free_rect.x + free_rect.width - right_x > EPS:
        new_rects.append(
            FreeRect(
                x=right_x,
                y=free_rect.y,
                width=(free_rect.x + free_rect.width) - right_x,
                length=free_rect.length,
            )
        )

    # bottom remainder
    if free_rect.y + free_rect.length - bottom_y > EPS:
        new_rects.append(
            FreeRect(
                x=free_rect.x,
                y=bottom_y,
                width=free_rect.width,
                length=(free_rect.y + free_rect.length) - bottom_y,
            )
        )

    return new_rects


def _score_fit(free_rect: FreeRect, w: float, l: float) -> Tuple[float, float, float]:
    leftover_area = free_rect.width * free_rect.length - w * l
    short_side = min(free_rect.width - w, free_rect.length - l)
    long_side = max(free_rect.width - w, free_rect.length - l)
    return (leftover_area, short_side, long_side)


def _place_on_board(board: BoardState, unit: PanelUnit, request: CuttingRequest, kerf: float) -> bool:
    best = None

    for rect_index, rect in enumerate(board.free_rects):
        for w, l, rotated in _candidate_orientations(unit, request):
            if w <= rect.width + EPS and l <= rect.length + EPS:
                score = _score_fit(rect, w, l)
                candidate = (score, rect_index, rect, w, l, rotated)

                if best is None or candidate[0] < best[0]:
                    best = candidate

    if best is None:
        return False

    _, rect_index, rect, w, l, rotated = best

    placed = PlacedPanel(
        panel_index=unit.panel_index,
        x=rect.x,
        y=rect.y,
        width=w,
        length=l,
        label=unit.panel.label,
        notes=unit.panel.notes,
        rotated=rotated,
        grain_aligned=unit.panel.alignment,
        board_number=board.board_number,
    )

    board.placed_panels.append(placed)
    board.used_area += w * l

    remaining_rects = board.free_rects[:rect_index] + board.free_rects[rect_index + 1 :]
    split_rects = _split_free_rect(rect, rect.x, rect.y, w, l, kerf)
    board.free_rects = _prune_free_rects(remaining_rects + split_rects)

    return True


def _validate_board_layouts(boards_work: List[BoardState], board_width: float, board_length: float) -> None:
    for b in boards_work:
        panels = b.placed_panels

        for p in panels:
            if p.x < -EPS or p.y < -EPS:
                raise ValueError(f"Invalid placement: negative position for panel '{p.label}'")
            if p.x + p.width > board_width + EPS:
                raise ValueError(f"Panel '{p.label}' exceeds board width")
            if p.y + p.length > board_length + EPS:
                raise ValueError(f"Panel '{p.label}' exceeds board length")

        for i in range(len(panels)):
            for j in range(i + 1, len(panels)):
                a = panels[i]
                c = panels[j]
                overlap = not (
                    a.x + a.width <= c.x + EPS
                    or c.x + c.width <= a.x + EPS
                    or a.y + a.length <= c.y + EPS
                    or c.y + c.length <= a.y + EPS
                )
                if overlap:
                    raise ValueError(
                        f"Overlap detected on board {b.board_number}: '{a.label}' and '{c.label}'"
                    )


def _generate_cuts_for_board(board: BoardState, kerf: float) -> List[CutSegment]:
    cuts: List[CutSegment] = []
    cut_id = 1
    xs = set()
    ys = set()

    for p in board.placed_panels:
        x_cut = p.x + p.width + (kerf / 2.0 if kerf > 0 else 0.0)
        y_cut = p.y + p.length + (kerf / 2.0 if kerf > 0 else 0.0)

        if x_cut < board.board_width - EPS:
            xs.add(round(x_cut, 4))
        if y_cut < board.board_length - EPS:
            ys.add(round(y_cut, 4))

    for x in sorted(xs):
        cuts.append(
            CutSegment(
                id=cut_id,
                orientation="vertical",
                direction="vertical",
                x1=x,
                y1=0.0,
                x2=x,
                y2=board.board_length,
                length=board.board_length,
                board_number=board.board_number,
                label=f"Rip cut at x={x:.1f}",
            )
        )
        cut_id += 1

    for y in sorted(ys):
        cuts.append(
            CutSegment(
                id=cut_id,
                orientation="horizontal",
                direction="horizontal",
                x1=0.0,
                y1=y,
                x2=board.board_width,
                y2=y,
                length=board.board_width,
                board_number=board.board_number,
                label=f"Cross cut at y={y:.1f}",
            )
        )
        cut_id += 1

    return cuts


def _build_edging_summary(request: CuttingRequest) -> EdgingSummary:
    total_edging_m = 0.0
    edging_details: List[EdgingDetail] = []

    for p in request.panels:
        edge_per_panel_m = p.edge_length_mm / 1000.0
        total_edge_m = p.total_edge_length_mm / 1000.0
        total_edging_m += total_edge_m

        edges_applied = "".join(
            side[0].upper()
            for side, flag in [
                ("top", p.edging.top),
                ("right", p.edging.right),
                ("bottom", p.edging.bottom),
                ("left", p.edging.left),
            ]
            if flag
        ) or "None"

        edging_details.append(
            EdgingDetail(
                panel_label=p.label or "Panel",
                quantity=int(p.quantity),
                edge_per_panel_m=edge_per_panel_m,
                total_edge_m=total_edge_m,
                edges_applied=edges_applied,
            )
        )

    return EdgingSummary(total_meters=total_edging_m, details=edging_details)


def _build_optimization_summary(
    request: CuttingRequest,
    boards: List[BoardLayout],
    total_used_area: float,
    impossible_panels: List[str],
    warnings: List[str],
    kerf_mm: float,
    board_width: float,
    board_length: float,
    total_panels: int,
    total_edging_m: float,
) -> OptimizationSummary:
    board_area = board_width * board_length
    total_waste_mm2 = sum(b.waste_area_mm2 for b in boards)
    total_board_area = board_area * max(len(boards), 1)

    total_waste_percent = total_waste_mm2 / total_board_area * 100.0 if total_board_area > 0 else 0.0
    overall_efficiency_percent = total_used_area / total_board_area * 100.0 if total_board_area > 0 else 0.0
    grain_considered = any(p.alignment != GrainAlignment.none for p in request.panels)
    total_cuts = sum(len(b.cuts) for b in boards)
    total_cut_length = sum(c.length for b in boards for c in b.cuts)

    return OptimizationSummary(
        total_boards=len(boards),
        total_panels=total_panels,
        unique_panel_types=len(request.panels),
        total_edging_meters=total_edging_m,
        total_cuts=total_cuts,
        total_cut_length=total_cut_length,
        total_waste_mm2=total_waste_mm2,
        total_waste_percent=total_waste_percent,
        board_width=board_width,
        board_length=board_length,
        total_used_area_mm2=total_used_area,
        overall_efficiency_percent=overall_efficiency_percent,
        kerf_mm=kerf_mm,
        grain_considered=grain_considered,
        material_groups=1,
        impossible_panels=impossible_panels,
        warnings=warnings,
    )


def run_optimization(
    request: CuttingRequest,
) -> Tuple[List[BoardLayout], OptimizationSummary, EdgingSummary, List[StickerLabel]]:
    _ensure_request_options(request)

    board_width, board_length = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)

    logger.info("Running improved free-rectangle optimizer")
    logger.info(f"Board size: {board_width} x {board_length}")
    logger.info(f"Kerf: {kerf}")

    units = _expand_panel_units(request)

    # Largest-first strategy helps reduce fragmentation
    units.sort(
        key=lambda u: (
            -u.area,
            -max(u.width, u.length),
            -min(u.width, u.length),
        )
    )

    boards_work: List[BoardState] = []
    impossible_units: List[PanelUnit] = []

    for unit in units:
        placed = False

        # Try all existing boards first
        best_board_index = None
        best_board_score = None

        for i, board in enumerate(boards_work):
            for rect in board.free_rects:
                for w, l, _ in _candidate_orientations(unit, request):
                    if w <= rect.width + EPS and l <= rect.length + EPS:
                        score = _score_fit(rect, w, l)
                        candidate = (score, i)
                        if best_board_score is None or candidate[0] < best_board_score:
                            best_board_score = candidate[0]
                            best_board_index = i

        if best_board_index is not None:
            placed = _place_on_board(boards_work[best_board_index], unit, request, kerf)

        # If not placed, open a new board
        if not placed:
            board_no = len(boards_work) + 1
            new_board = BoardState(
                board_number=board_no,
                board_width=board_width,
                board_length=board_length,
            )
            placed = _place_on_board(new_board, unit, request, kerf)

            if placed:
                boards_work.append(new_board)
            else:
                impossible_units.append(unit)

    if not request.options or getattr(request.options, "strict_validation", True):
        _validate_board_layouts(boards_work, board_width, board_length)

    boards: List[BoardLayout] = []
    total_used_area = 0.0

    for b in boards_work:
        used = float(b.used_area)
        waste = max(board_width * board_length - used, 0.0)
        eff = used / (board_width * board_length) * 100.0 if board_width * board_length > 0 else 0.0
        total_used_area += used

        cuts = _generate_cuts_for_board(b, kerf) if getattr(request.options, "generate_cuts", True) else []

        boards.append(
            BoardLayout(
                board_number=b.board_number,
                board_width=board_width,
                board_length=board_length,
                used_area_mm2=used,
                waste_area_mm2=waste,
                efficiency_percent=eff,
                panel_count=len(b.placed_panels),
                panels=b.placed_panels,
                cuts=cuts,
            )
        )

    impossible_panels = [u.label for u in impossible_units]
    warnings = []
    if impossible_panels:
        warnings.append(f"{len(impossible_panels)} panel unit(s) could not be placed.")

    edging = _build_edging_summary(request)

    summary = _build_optimization_summary(
        request=request,
        boards=boards,
        total_used_area=total_used_area,
        impossible_panels=impossible_panels,
        warnings=warnings,
        kerf_mm=kerf,
        board_width=board_width,
        board_length=board_length,
        total_panels=sum(int(p.quantity) for p in request.panels),
        total_edging_m=edging.total_meters,
    )

    stickers: List[StickerLabel] = []
    serial_counter = 1

    for board in boards:
        for panel in board.panels:
            stickers.append(
                StickerLabel(
                    serial_number=f"LBL-{board.board_number}-{serial_counter:04d}",
                    panel_label=panel.label or "Panel",
                    width=panel.width,
                    length=panel.length,
                    board_number=board.board_number,
                    x=panel.x,
                    y=panel.y,
                    rotated=panel.rotated,
                    project_name=request.project_name,
                    customer_name=request.customer_name,
                    board_type=request.board.board_type,
                    thickness_mm=request.board.thickness_mm,
                    company=request.board.company,
                    color_name=request.board.color_name,
                    notes=panel.notes,
                    qr_url=None,
                )
            )
            serial_counter += 1

    return boards, summary, edging, stickers
