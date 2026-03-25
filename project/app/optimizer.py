from __future__ import annotations

from dataclasses import dataclass, field
from collections import Counter
from typing import Dict, List, Optional, Tuple
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
)

logger = logging.getLogger("panelpro")

EPS = 1e-6
TRIM_MARGIN_MM = 0.0

MIN_REUSABLE_WIDTH_MM = 180.0
MIN_REUSABLE_LENGTH_MM = 300.0
SLIVER_WIDTH_MM = 120.0
SLIVER_LENGTH_MM = 220.0


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

    def clone(self) -> "BoardState":
        return BoardState(
            board_number=self.board_number,
            board_width=self.board_width,
            board_length=self.board_length,
            placed_panels=[p.model_copy(deep=True) for p in self.placed_panels],
            used_area=self.used_area,
        )


def _ensure_request_options(request: CuttingRequest) -> None:
    if request.options is None:
        request.options = Options()


def _resolve_board_size(request: CuttingRequest) -> Tuple[float, float]:
    board_width = float(request.board.width_mm)
    board_length = float(request.board.length_mm)
    return (
        board_width - 2.0 * TRIM_MARGIN_MM,
        board_length - 2.0 * TRIM_MARGIN_MM,
    )


def _get_kerf_mm(request: CuttingRequest) -> float:
    if request.options is None:
        return 3.0
    return float(request.options.kerf or 3.0)


def _panel_can_rotate(panel, request: CuttingRequest) -> bool:
    if request.options and not request.options.allow_rotation:
        return False
    if request.options and request.options.consider_grain:
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


def _unit_sort_key(unit: PanelUnit, request: CuttingRequest) -> Tuple:
    board_width, board_length = _resolve_board_size(request)
    orientations = _candidate_orientations(unit, request)
    full_width = any(abs(w - board_width) < EPS for w, _, _ in orientations)
    full_length = any(abs(l - board_length) < EPS for _, l, _ in orientations)
    max_l = max(l for _, l, _ in orientations)
    max_w = max(w for w, _, _ in orientations)
    min_w = min(w for w, _, _ in orientations)

    return (
        0 if full_width else 1,
        0 if full_length else 1,
        -max_l,
        -max_w,
        min_w,
        -unit.area,
    )


def _validate_board_layouts(boards_work: List[BoardState], board_width: float, board_length: float) -> None:
    for b in boards_work:
        panels = b.placed_panels
        for p in panels:
            if p.x < -EPS or p.y < -EPS:
                raise ValueError(f"Invalid placement: negative position for panel '{p.label}'")
            if p.x + p.width > board_width + EPS:
                raise ValueError(f"Panel '{p.label}' exceeds board width: {p.x + p.width} > {board_width}")
            if p.y + p.length > board_length + EPS:
                raise ValueError(f"Panel '{p.label}' exceeds board length: {p.y + p.length} > {board_length}")

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


def _is_reusable_rect(w: float, l: float) -> bool:
    return w >= MIN_REUSABLE_WIDTH_MM and l >= MIN_REUSABLE_LENGTH_MM


def _is_sliver_rect(w: float, l: float) -> bool:
    return w < SLIVER_WIDTH_MM or l < SLIVER_LENGTH_MM


def _offcut_score_from_board(board: BoardState) -> Tuple:
    waste = max(board.board_width * board.board_length - board.used_area, 0.0)
    reusable_bonus = waste if waste >= MIN_REUSABLE_WIDTH_MM * MIN_REUSABLE_LENGTH_MM else 0.0
    sliver_penalty = 0
    return (
        sliver_penalty,
        -reusable_bonus,
        waste,
        len(board.placed_panels),
    )


def _compute_impossible_from_solution(request: CuttingRequest, boards: List[BoardState]) -> List[PanelUnit]:
    placed = Counter()
    for b in boards:
        for p in b.placed_panels:
            placed[p.panel_index] += 1

    impossible: List[PanelUnit] = []
    uid = 1
    for idx, pd in enumerate(request.panels):
        qty = int(pd.quantity)
        missing = max(0, qty - placed[idx])
        for _ in range(missing):
            impossible.append(
                PanelUnit(
                    panel_index=idx,
                    panel=pd,
                    unit_id=uid,
                    width=float(pd.width),
                    length=float(pd.length),
                    area=float(pd.width) * float(pd.length),
                    label=pd.label or f"Panel-{idx + 1}",
                )
            )
            uid += 1
    return impossible


def _pack_horizontal_strips(
    request: CuttingRequest,
    units: List[PanelUnit],
    kerf: float,
) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    warnings: List[str] = []
    remaining = sorted(units, key=lambda u: _unit_sort_key(u, request))
    boards: List[BoardState] = []
    board_w, board_l = _resolve_board_size(request)

    while remaining:
        board_no = len(boards) + 1
        board = BoardState(board_number=board_no, board_width=board_w, board_length=board_l)
        y = TRIM_MARGIN_MM
        placed_ids = set()

        while True:
            available = [u for u in remaining if u.unit_id not in placed_ids]
            if not available:
                break

            candidate_heights = []
            for u in available:
                for w, l, _ in _candidate_orientations(u, request):
                    if l <= board_l - (y - TRIM_MARGIN_MM) + EPS:
                        candidate_heights.append(l)

            if not candidate_heights:
                break

            best_row = None
            best_score = None

            for row_h in sorted(set(round(h, 6) for h in candidate_heights), reverse=True):
                x = TRIM_MARGIN_MM
                row = []
                row_area = 0.0
                used_local = set()

                for u in available:
                    if u.unit_id in used_local:
                        continue

                    chosen = None
                    for w, l, rotated in _candidate_orientations(u, request):
                        if abs(l - row_h) < EPS:
                            add = w + (kerf if x > TRIM_MARGIN_MM else 0.0)
                            if x + add <= TRIM_MARGIN_MM + board_w + EPS:
                                chosen = (w, l, rotated)
                                break

                    if chosen is None:
                        continue

                    w, l, rotated = chosen
                    px = x + (kerf if x > TRIM_MARGIN_MM else 0.0)
                    row.append((u, px, y, w, l, rotated))
                    row_area += w * l
                    used_local.add(u.unit_id)
                    x = px + w

                if not row:
                    continue

                leftover_w = max(TRIM_MARGIN_MM + board_w - x, 0.0)
                score = (
                    0 if leftover_w < EPS else 1,
                    0 if _is_reusable_rect(leftover_w, row_h) else 1,
                    leftover_w,
                    -row_area,
                    -len(row),
                    -row_h,
                )

                if best_row is None or score < best_score:
                    best_row = row
                    best_score = score

            if not best_row:
                break

            row_h = best_row[0][4]
            if y + row_h > TRIM_MARGIN_MM + board_l + EPS:
                break

            for u, px, py, w, l, rotated in best_row:
                board.placed_panels.append(
                    PlacedPanel(
                        panel_index=u.panel_index,
                        x=px,
                        y=py,
                        width=w,
                        length=l,
                        label=u.panel.label,
                        notes=u.panel.notes,
                        rotated=rotated,
                        grain_aligned=u.panel.alignment,
                        board_number=board_no,
                    )
                )
                board.used_area += w * l
                placed_ids.add(u.unit_id)

            y += row_h + kerf
            if y > TRIM_MARGIN_MM + board_l + EPS:
                break

        if not placed_ids:
            break

        boards.append(board)
        remaining = [u for u in remaining if u.unit_id not in placed_ids]

    if remaining:
        warnings.append(f"{len(remaining)} panel unit(s) could not be placed in horizontal-strip strategy.")

    return boards, remaining, warnings


def _pack_vertical_strips(
    request: CuttingRequest,
    units: List[PanelUnit],
    kerf: float,
) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    warnings: List[str] = []
    remaining = sorted(units, key=lambda u: _unit_sort_key(u, request))
    boards: List[BoardState] = []
    board_w, board_l = _resolve_board_size(request)

    while remaining:
        board_no = len(boards) + 1
        board = BoardState(board_number=board_no, board_width=board_w, board_length=board_l)
        x = TRIM_MARGIN_MM
        placed_ids = set()

        while True:
            available = [u for u in remaining if u.unit_id not in placed_ids]
            if not available:
                break

            candidate_widths = []
            for u in available:
                for w, l, _ in _candidate_orientations(u, request):
                    if w <= board_w - (x - TRIM_MARGIN_MM) + EPS:
                        candidate_widths.append(w)

            if not candidate_widths:
                break

            best_col = None
            best_score = None

            for col_w in sorted(set(round(w, 6) for w in candidate_widths), reverse=True):
                y = TRIM_MARGIN_MM
                col = []
                col_area = 0.0
                used_local = set()

                for u in available:
                    if u.unit_id in used_local:
                        continue

                    chosen = None
                    for w, l, rotated in _candidate_orientations(u, request):
                        if abs(w - col_w) < EPS:
                            add = l + (kerf if y > TRIM_MARGIN_MM else 0.0)
                            if y + add <= TRIM_MARGIN_MM + board_l + EPS:
                                chosen = (w, l, rotated)
                                break

                    if chosen is None:
                        continue

                    w, l, rotated = chosen
                    py = y + (kerf if y > TRIM_MARGIN_MM else 0.0)
                    col.append((u, x, py, w, l, rotated))
                    col_area += w * l
                    used_local.add(u.unit_id)
                    y = py + l

                if not col:
                    continue

                leftover_l = max(TRIM_MARGIN_MM + board_l - y, 0.0)
                score = (
                    0 if leftover_l < EPS else 1,
                    0 if _is_reusable_rect(col_w, leftover_l) else 1,
                    leftover_l,
                    -col_area,
                    -len(col),
                    -col_w,
                )

                if best_col is None or score < best_score:
                    best_col = col
                    best_score = score

            if not best_col:
                break

            col_w = best_col[0][3]
            if x + col_w > TRIM_MARGIN_MM + board_w + EPS:
                break

            for u, px, py, w, l, rotated in best_col:
                board.placed_panels.append(
                    PlacedPanel(
                        panel_index=u.panel_index,
                        x=px,
                        y=py,
                        width=w,
                        length=l,
                        label=u.panel.label,
                        notes=u.panel.notes,
                        rotated=rotated,
                        grain_aligned=u.panel.alignment,
                        board_number=board_no,
                    )
                )
                board.used_area += w * l
                placed_ids.add(u.unit_id)

            x += col_w + kerf
            if x > TRIM_MARGIN_MM + board_w + EPS:
                break

        if not placed_ids:
            break

        boards.append(board)
        remaining = [u for u in remaining if u.unit_id not in placed_ids]

    if remaining:
        warnings.append(f"{len(remaining)} panel unit(s) could not be placed in vertical-strip strategy.")

    return boards, remaining, warnings


def _pack_shelf_fallback(
    request: CuttingRequest,
    units: List[PanelUnit],
    kerf: float,
) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    warnings: List[str] = []

    @dataclass
    class Shelf:
        y: float
        height: float
        used_width: float = 0.0

    boards: List[BoardState] = []
    shelf_map: Dict[int, List[Shelf]] = {}
    remaining_units = sorted(units, key=lambda u: _unit_sort_key(u, request))
    impossible: List[PanelUnit] = []

    board_w, board_l = _resolve_board_size(request)

    def try_place(board: BoardState, unit: PanelUnit) -> bool:
        shelves = shelf_map.setdefault(board.board_number, [])
        best = None

        for w, l, rotated in _candidate_orientations(unit, request):
            for idx, shelf in enumerate(shelves):
                x = shelf.used_width + (kerf if shelf.used_width > 0 else 0.0)
                if l <= shelf.height + EPS and x + w <= board_w + EPS:
                    score = (shelf.height - l, board_w - (x + w))
                    if best is None or score < best[0]:
                        best = (score, "existing", idx, w, l, rotated)

            used_height = shelves[-1].y + shelves[-1].height + kerf if shelves else TRIM_MARGIN_MM
            if used_height + l <= board_l + TRIM_MARGIN_MM + EPS and w <= board_w + EPS:
                score = (0, board_w - w, board_l - (used_height + l))
                if best is None or score < best[0]:
                    best = (score, "new", None, w, l, rotated)

        if best is None:
            return False

        _, mode, idx, w, l, rotated = best
        shelves = shelf_map.setdefault(board.board_number, [])

        if mode == "existing":
            shelf = shelves[idx]
            x = shelf.used_width + (kerf if shelf.used_width > 0 else 0.0)
            board.placed_panels.append(
                PlacedPanel(
                    panel_index=unit.panel_index,
                    x=x,
                    y=shelf.y,
                    width=w,
                    length=l,
                    label=unit.panel.label,
                    notes=unit.panel.notes,
                    rotated=rotated,
                    grain_aligned=unit.panel.alignment,
                    board_number=board.board_number,
                )
            )
            shelf.used_width = x + w
            board.used_area += w * l
            return True

        y = shelves[-1].y + shelves[-1].height + kerf if shelves else TRIM_MARGIN_MM
        shelf = Shelf(y=y, height=l, used_width=TRIM_MARGIN_MM + w)
        shelves.append(shelf)
        board.placed_panels.append(
            PlacedPanel(
                panel_index=unit.panel_index,
                x=TRIM_MARGIN_MM,
                y=y,
                width=w,
                length=l,
                label=unit.panel.label,
                notes=unit.panel.notes,
                rotated=rotated,
                grain_aligned=unit.panel.alignment,
                board_number=board.board_number,
            )
        )
        board.used_area += w * l
        return True

    for unit in remaining_units:
        placed = False
        best_choice = None

        for idx, board in enumerate(boards):
            test_board = board.clone()
            test_shelves = [Shelf(s.y, s.height, s.used_width) for s in shelf_map.get(board.board_number, [])]
            shelf_map[test_board.board_number] = test_shelves

            if try_place(test_board, unit):
                score = (-(test_board.used_area), len(test_shelves), idx)
                if best_choice is None or score < best_choice[0]:
                    best_choice = (score, idx, test_board, test_shelves)

        if best_choice is not None:
            _, idx, new_board, new_shelves = best_choice
            boards[idx] = new_board
            shelf_map[new_board.board_number] = new_shelves
            placed = True

        if not placed:
            board_no = len(boards) + 1
            new_board = BoardState(board_number=board_no, board_width=board_w, board_length=board_l)
            shelf_map[board_no] = []
            if try_place(new_board, unit):
                boards.append(new_board)
                placed = True

        if not placed:
            impossible.append(unit)

    if impossible:
        warnings.append(f"{len(impossible)} panel unit(s) could not be placed in shelf fallback.")

    return boards, impossible, warnings


def _solution_key(boards: List[BoardState], impossible: List[PanelUnit]) -> Tuple:
    total_used = sum(b.used_area for b in boards)
    total_board_area = sum(b.board_width * b.board_length for b in boards)
    waste = total_board_area - total_used
    offcut_scores = [_offcut_score_from_board(b) for b in boards]
    combined_offcut = tuple(sum(vals) for vals in zip(*offcut_scores)) if offcut_scores else (0, 0, 0, 0)

    return (
        len(impossible),
        len(boards),
        combined_offcut,
        waste,
    )


def _choose_best_solution(
    solutions: List[Tuple[str, List[BoardState], List[PanelUnit], List[str]]]
) -> Tuple[List[BoardState], List[PanelUnit], List[str]]:
    valid = [s for s in solutions if s[1] or not s[2]]
    if not valid:
        valid = solutions

    best = None
    best_key = None
    best_name = None

    for name, boards, impossible, warnings in valid:
        key = _solution_key(boards, impossible)
        logger.info(f"Solution {name}: boards={len(boards)}, impossible={len(impossible)}, key={key}")
        if best is None or key < best_key:
            best = (boards, impossible, warnings)
            best_key = key
            best_name = name

    logger.info(f"Selected solution engine: {best_name}, key={best_key}")
    return best


def _generate_cuts_for_board(board: BoardState, kerf: float) -> List[CutSegment]:
    cuts: List[CutSegment] = []
    cut_id = 1

    xs = set()
    ys = set()

    for p in board.placed_panels:
        x_cut = p.x + p.width + (kerf / 2.0 if kerf > 0 else 0.0)
        y_cut = p.y + p.length + (kerf / 2.0 if kerf > 0 else 0.0)

        if x_cut < (TRIM_MARGIN_MM + board.board_width) - EPS:
            xs.add(round(x_cut, 4))
        if y_cut < (TRIM_MARGIN_MM + board.board_length) - EPS:
            ys.add(round(y_cut, 4))

    for x in sorted(xs):
        cuts.append(
            CutSegment(
                id=cut_id,
                orientation="vertical",
                direction="vertical",
                x1=x,
                y1=TRIM_MARGIN_MM,
                x2=x,
                y2=TRIM_MARGIN_MM + board.board_length,
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
                x1=TRIM_MARGIN_MM,
                y1=y,
                x2=TRIM_MARGIN_MM + board.board_width,
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


def _work_to_layouts(
    request: CuttingRequest,
    boards_work: List[BoardState],
    impossible_units: List[PanelUnit],
    warnings: Optional[List[str]] = None,
) -> Tuple[List[BoardLayout], OptimizationSummary, EdgingSummary]:
    board_width, board_length = _resolve_board_size(request)
    board_area = board_width * board_length
    kerf = _get_kerf_mm(request)

    warnings = warnings or []
    boards_work = [b for b in boards_work if b.used_area > EPS]

    if not request.options or request.options.strict_validation:
        _validate_board_layouts(boards_work, TRIM_MARGIN_MM + board_width, TRIM_MARGIN_MM + board_length)

    boards: List[BoardLayout] = []
    total_used_area = 0.0

    for b in boards_work:
        used = float(b.used_area)
        waste = max(board_area - used, 0.0)
        eff = used / board_area * 100.0 if board_area > 0 else 0.0
        total_used_area += used
        cuts = _generate_cuts_for_board(b, kerf) if (not request.options or request.options.generate_cuts) else []

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
    edging = _build_edging_summary(request)
    summary = _build_optimization_summary(
        request=request,
        boards=boards,
        total_used_area=total_used_area,
        impossible_panels=impossible_panels,
        warnings=warnings + [f"Final production optimizer applied for {int(board_length)}x{int(board_width)} boards"],
        kerf_mm=kerf,
        board_width=board_width,
        board_length=board_length,
        total_panels=sum(int(p.quantity) for p in request.panels),
        total_edging_m=edging.total_meters,
    )
    return boards, summary, edging


def run_optimization(
    request: CuttingRequest,
) -> Tuple[List[BoardLayout], OptimizationSummary, EdgingSummary, list]:
    _ensure_request_options(request)
    board_width, board_length = _resolve_board_size(request)
    kerf = _get_kerf_mm(request)

    logger.info("Running final production optimizer")
    logger.info(f"Usable board size: {board_width} x {board_length} mm")
    logger.info(f"Kerf: {kerf} mm")

    units = _expand_panel_units(request)

    solutions = [
        ("horizontal_strips", *_pack_horizontal_strips(request, units, kerf)),
        ("vertical_strips", *_pack_vertical_strips(request, units, kerf)),
        ("shelf", *_pack_shelf_fallback(request, units, kerf)),
    ]

    boards_work, impossible_units, warnings = _choose_best_solution(solutions)

    boards, summary, edging = _work_to_layouts(
        request=request,
        boards_work=boards_work,
        impossible_units=impossible_units,
        warnings=warnings,
    )

    stickers = []
    serial_counter = 1

    for board in boards:
        for panel in board.panels:
            stickers.append(
                {
                    "serial_number": f"LBL-{board.board_number}-{serial_counter:04d}",
                    "panel_label": panel.label or "Panel",
                    "width": panel.width,
                    "length": panel.length,
                    "board_number": board.board_number,
                    "x": panel.x,
                    "y": panel.y,
                    "rotated": panel.rotated,
                    "project_name": request.project_name,
                    "customer_name": request.customer_name,
                    "board_type": request.board.board_type,
                    "thickness_mm": request.board.thickness_mm,
                    "company": request.board.company,
                    "color_name": request.board.color_name,
                    "notes": panel.notes,
                    "qr_url": None,
                }
            )
            serial_counter += 1

    return boards, summary, edging, stickers
