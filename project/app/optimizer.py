from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Tuple, Optional, Any, Dict
from collections import defaultdict
import logging

from .schemas import (
    CuttingRequest,
    BoardLayout,
    PlacedPanel,
    OptimizationSummary,
    EdgingSummary,
    EdgingDetail,
    GrainAlignment,
    CutSegment,
    BoardSelection,
    StickerLabel,
)
from .config import (
    DEFAULT_BOARD_WIDTH_MM,
    DEFAULT_BOARD_LENGTH_MM,
    COMPANY_NAME,
    COMPANY_LOGO_PATH,
)

logger = logging.getLogger(__name__)

COMPANY_LOGO_URL = "/static/logo.png"


class PlacementHeuristic:
    BEST_SHORT_SIDE_FIT = "best_short_side_fit"
    BEST_LONG_SIDE_FIT = "best_long_side_fit"
    BEST_AREA_FIT = "best_area_fit"


class SortStrategy:
    AREA_DESC = "area_desc"
    LONGEST_SIDE_DESC = "longest_side_desc"
    WIDTH_DESC = "width_desc"
    LENGTH_DESC = "length_desc"
    PERIMETER_DESC = "perimeter_desc"


@dataclass
class CandidatePlacement:
    free_rect_index: int
    x: float
    y: float
    footprint_width: float
    footprint_length: float
    rotated: bool
    score1: float
    score2: float


class FreeRect:
    __slots__ = ("x", "y", "w", "h")

    def __init__(self, x: float, y: float, w: float, h: float):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def area(self) -> float:
        return self.w * self.h

    def intersects(self, other: "FreeRect") -> bool:
        return not (
            self.x >= other.x + other.w
            or self.x + self.w <= other.x
            or self.y >= other.y + other.h
            or self.y + self.h <= other.y
        )

    def contains(self, other: "FreeRect") -> bool:
        return (
            other.x >= self.x
            and other.y >= self.y
            and other.x + other.w <= self.x + self.w
            and other.y + other.h <= self.y + self.h
        )


class StockTemplate:
    def __init__(self, width: float, length: float, qty: Optional[int] = None):
        self.width = width
        self.length = length
        self.qty = qty


class Board:
    def __init__(
        self,
        board_number: int,
        width: float,
        length: float,
        material: Optional[BoardSelection] = None,
        source: str = "new",
    ):
        self.board_number = board_number
        self.width = width
        self.length = length
        self.material = material
        self.source = source
        self.free_rects: List[FreeRect] = [FreeRect(0, 0, width, length)]
        self.placed_panels: List[PlacedPanel] = []
        self.used_area = 0.0

    def area(self) -> float:
        return self.width * self.length

    def waste_area(self) -> float:
        return self.area() - self.used_area

    def efficiency(self) -> float:
        return (self.used_area / self.area()) * 100.0 if self.area() > 0 else 0.0

    def find_best_placement(
        self,
        panel: Any,
        kerf: float,
        heuristic: str,
        consider_grain: bool,
    ) -> Optional[CandidatePlacement]:
        orientations = get_allowed_orientations(panel, kerf, consider_grain)
        best: Optional[CandidatePlacement] = None

        for fr_idx, fr in enumerate(self.free_rects):
            for footprint_w, footprint_l, rotated in orientations:
                if footprint_w <= fr.w and footprint_l <= fr.h:
                    score1, score2 = score_fit(fr, footprint_w, footprint_l, heuristic)
                    candidate = CandidatePlacement(
                        free_rect_index=fr_idx,
                        x=fr.x,
                        y=fr.y,
                        footprint_width=footprint_w,
                        footprint_length=footprint_l,
                        rotated=rotated,
                        score1=score1,
                        score2=score2,
                    )
                    if best is None or (candidate.score1, candidate.score2) < (best.score1, best.score2):
                        best = candidate
        return best

    def place_candidate(self, panel_idx: int, panel: Any, candidate: CandidatePlacement):
        actual_width = panel.length if candidate.rotated else panel.width
        actual_length = panel.width if candidate.rotated else panel.length

        placed = PlacedPanel(
            panel_index=panel_idx,
            x=candidate.x,
            y=candidate.y,
            width=actual_width,
            length=actual_length,
            footprint_width=candidate.footprint_width,
            footprint_length=candidate.footprint_length,
            original_width=panel.width,
            original_length=panel.length,
            rotated=candidate.rotated,
            label=panel.label,
            notes=panel.notes,
            grain_aligned=panel.alignment,
        )

        self.placed_panels.append(placed)
        self.used_area += candidate.footprint_width * candidate.footprint_length

        used_rect = FreeRect(
            candidate.x,
            candidate.y,
            candidate.footprint_width,
            candidate.footprint_length,
        )
        self._split_all_intersecting_free_rects(used_rect)
        self._prune_free_rects()

    def _split_all_intersecting_free_rects(self, used: FreeRect):
        new_rects: List[FreeRect] = []

        for fr in self.free_rects:
            if not fr.intersects(used):
                new_rects.append(fr)
                continue

            if used.y > fr.y:
                new_rects.append(FreeRect(fr.x, fr.y, fr.w, used.y - fr.y))
            if used.y + used.h < fr.y + fr.h:
                new_rects.append(
                    FreeRect(fr.x, used.y + used.h, fr.w, (fr.y + fr.h) - (used.y + used.h))
                )
            if used.x > fr.x:
                new_rects.append(FreeRect(fr.x, fr.y, used.x - fr.x, fr.h))
            if used.x + used.w < fr.x + fr.w:
                new_rects.append(
                    FreeRect(used.x + used.w, fr.y, (fr.x + fr.w) - (used.x + used.w), fr.h)
                )

        self.free_rects = [r for r in new_rects if r.w > 0 and r.h > 0]

    def _prune_free_rects(self):
        pruned: List[FreeRect] = []
        for i, rect in enumerate(self.free_rects):
            contained = False
            for j, other in enumerate(self.free_rects):
                if i != j and other.contains(rect):
                    contained = True
                    break
            if not contained:
                pruned.append(rect)

        unique = {}
        for r in pruned:
            key = (round(r.x, 6), round(r.y, 6), round(r.w, 6), round(r.h, 6))
            unique[key] = r

        self.free_rects = list(unique.values())


def material_signature(board: BoardSelection) -> Tuple:
    return (
        board.board_item_id,
        board.board_type.strip().lower(),
        int(board.thickness_mm),
        board.company.strip().lower(),
        board.color_name.strip().lower(),
        float(board.width_mm),
        float(board.length_mm),
    )


def get_allowed_orientations(panel: Any, kerf: float, consider_grain: bool):
    normal_w = panel.width + kerf
    normal_l = panel.length + kerf

    rotated_w = panel.length + kerf
    rotated_l = panel.width + kerf

    if panel.alignment == GrainAlignment.horizontal:
        return [(normal_w, normal_l, False)]

    if panel.alignment == GrainAlignment.vertical:
        return [(rotated_w, rotated_l, True)]

    return [
        (normal_w, normal_l, False),
        (rotated_w, rotated_l, True),
    ]


def score_fit(fr: FreeRect, w: float, h: float, heuristic: str) -> Tuple[float, float]:
    leftover_w = abs(fr.w - w)
    leftover_h = abs(fr.h - h)
    short_side = min(leftover_w, leftover_h)
    long_side = max(leftover_w, leftover_h)
    area_fit = fr.area() - (w * h)

    if heuristic == PlacementHeuristic.BEST_SHORT_SIDE_FIT:
        return short_side, long_side
    if heuristic == PlacementHeuristic.BEST_LONG_SIDE_FIT:
        return long_side, short_side
    return area_fit, short_side


def expand_panels(request: CuttingRequest) -> List[Tuple[int, Any]]:
    expanded = []
    for idx, panel in enumerate(request.panels):
        for _ in range(panel.quantity):
            expanded.append((idx, panel))
    return expanded


def sort_panels(panel_instances: List[Tuple[int, Any]], strategy: str) -> List[Tuple[int, Any]]:
    if strategy == SortStrategy.AREA_DESC:
        return sorted(panel_instances, key=lambda x: x[1].width * x[1].length, reverse=True)
    if strategy == SortStrategy.LONGEST_SIDE_DESC:
        return sorted(panel_instances, key=lambda x: max(x[1].width, x[1].length), reverse=True)
    if strategy == SortStrategy.WIDTH_DESC:
        return sorted(panel_instances, key=lambda x: x[1].width, reverse=True)
    if strategy == SortStrategy.LENGTH_DESC:
        return sorted(panel_instances, key=lambda x: x[1].length, reverse=True)
    if strategy == SortStrategy.PERIMETER_DESC:
        return sorted(panel_instances, key=lambda x: 2 * (x[1].width + x[1].length), reverse=True)
    return panel_instances


def build_stock_templates(request: CuttingRequest) -> List[StockTemplate]:
    if request.stock_sheets:
        return [StockTemplate(width=s.width, length=s.length, qty=s.qty) for s in request.stock_sheets]
    return [
        StockTemplate(
            width=float(request.board.width_mm or DEFAULT_BOARD_WIDTH_MM),
            length=float(request.board.length_mm or DEFAULT_BOARD_LENGTH_MM),
            qty=None,
        )
    ]


def validate_panels_fit(panel_instances, stock_templates, kerf, consider_grain):
    for _, panel in panel_instances:
        fits_any = False
        orientations = get_allowed_orientations(panel, kerf, consider_grain)
        for stock in stock_templates:
            for w, l, _ in orientations:
                if w <= stock.width and l <= stock.length:
                    fits_any = True
                    break
            if fits_any:
                break
        if not fits_any:
            raise ValueError(
                f"Panel '{panel.label or '?'}' ({panel.width} x {panel.length}) cannot fit into available stock."
            )


def make_global_stock_remaining(stock_templates: List[StockTemplate]) -> Dict[Tuple[float, float], Optional[int]]:
    stock_remaining: Dict[Tuple[float, float], Optional[int]] = {}
    for stock in stock_templates:
        key = (stock.width, stock.length)
        if key in stock_remaining:
            if stock_remaining[key] is None or stock.qty is None:
                stock_remaining[key] = None
            else:
                stock_remaining[key] += stock.qty
        else:
            stock_remaining[key] = stock.qty
    return stock_remaining


def deduct_stock_usage(stock_remaining: Dict[Tuple[float, float], Optional[int]], width: float, length: float):
    key = (width, length)
    remaining = stock_remaining.get(key)
    if remaining is None:
        return
    if remaining <= 0:
        raise RuntimeError(f"No remaining stock for board size {width} x {length}")
    stock_remaining[key] = remaining - 1


def material_to_dict(material: Optional[BoardSelection]) -> Optional[Dict[str, Any]]:
    if not material:
        return None
    return {
        "board_item_id": material.board_item_id,
        "board_type": material.board_type,
        "thickness_mm": material.thickness_mm,
        "company": material.company,
        "color_name": material.color_name,
        "width_mm": material.width_mm,
        "length_mm": material.length_mm,
        "price_per_board": material.price_per_board,
    }


def generate_simple_cuts_for_board(board: Board) -> List[CutSegment]:
    cuts: List[CutSegment] = []
    cut_id = 1
    seen_v = set()
    seen_h = set()

    for p in board.placed_panels:
        vx = round(p.x + p.footprint_width, 4)
        hy = round(p.y + p.footprint_length, 4)

        if 0 < vx < board.width and vx not in seen_v:
            seen_v.add(vx)
            cuts.append(
                CutSegment(
                    id=cut_id,
                    orientation="V",
                    x1=vx,
                    y1=0,
                    x2=vx,
                    y2=board.length,
                    length=board.length,
                    board_number=board.board_number,
                    sequence=cut_id,
                )
            )
            cut_id += 1

        if 0 < hy < board.length and hy not in seen_h:
            seen_h.add(hy)
            cuts.append(
                CutSegment(
                    id=cut_id,
                    orientation="H",
                    x1=0,
                    y1=hy,
                    x2=board.width,
                    y2=hy,
                    length=board.width,
                    board_number=board.board_number,
                    sequence=cut_id,
                )
            )
            cut_id += 1

    return cuts


def datetime_now_year() -> int:
    from datetime import datetime
    return datetime.utcnow().year


def generate_stickers(request: CuttingRequest, board_layouts: List[BoardLayout]) -> List[StickerLabel]:
    stickers: List[StickerLabel] = []
    serial_counter = 1
    frontend_public_url = os.getenv("FRONTEND_PUBLIC_URL", "http://localhost:5173").rstrip("/")
    company_phone = os.getenv("COMPANY_PHONE", "")

    for board in board_layouts:
        for panel in board.panels:
            material = board.material or {}
            serial_number = f"PNL-{datetime_now_year()}-{serial_counter:05d}"

            # HASH-BASED ROUTE
            qr_url = f"{frontend_public_url}/#/track/{serial_number}"

            logger.info("QR URL GENERATED: %s", qr_url)

            stickers.append(
                StickerLabel(
                    serial_number=serial_number,
                    panel_label=panel.label or f"Panel {panel.panel_index + 1}",
                    width=panel.width,
                    length=panel.length,
                    board_number=board.board_number,
                    x=panel.x,
                    y=panel.y,
                    rotated=panel.rotated,
                    project_name=request.project_name,
                    customer_name=request.customer_name,
                    company_name=COMPANY_NAME,
                    company_logo_url=COMPANY_LOGO_URL,
                    company_phone=company_phone,
                    board_type=material.get("board_type"),
                    thickness_mm=material.get("thickness_mm"),
                    company=material.get("company"),
                    color_name=material.get("color_name"),
                    notes=panel.notes,
                    qr_url=qr_url,
                )
            )
            serial_counter += 1

    return stickers


def evaluate_boards(boards: List[Board]) -> Tuple[int, float, float]:
    used_boards = [b for b in boards if b.placed_panels]
    total_boards = len(used_boards)
    total_board_area = sum(b.area() for b in used_boards)
    total_waste = sum(b.waste_area() for b in used_boards)
    waste_percent = (total_waste / total_board_area) * 100 if total_board_area > 0 else 0.0
    return total_boards, total_waste, waste_percent


def optimize_group(group_panels, group_material, stock_templates, stock_remaining, heuristic, sort_strategy, kerf, consider_grain, starting_board_number):
    panel_instances = sort_panels(group_panels, sort_strategy)
    boards: List[Board] = []
    next_board_number = starting_board_number

    for idx, panel in panel_instances:
        best_candidate = None
        best_board = None

        for board in boards:
            candidate = board.find_best_placement(panel, kerf, heuristic, consider_grain)
            if candidate:
                if best_candidate is None or (candidate.score1, candidate.score2) < (best_candidate.score1, best_candidate.score2):
                    best_candidate = candidate
                    best_board = board

        if best_candidate is not None and best_board is not None:
            best_board.place_candidate(idx, panel, best_candidate)
            continue

        best_new_board = None
        best_new_candidate = None

        for stock in stock_templates:
            remaining = stock_remaining.get((stock.width, stock.length))
            if remaining is not None and remaining <= 0:
                continue

            temp_board = Board(
                board_number=next_board_number,
                width=stock.width,
                length=stock.length,
                material=group_material,
                source="new",
            )

            candidate = temp_board.find_best_placement(panel, kerf, heuristic, consider_grain)
            if candidate:
                if best_new_candidate is None or (candidate.score1, candidate.score2) < (best_new_candidate.score1, best_new_candidate.score2):
                    best_new_candidate = candidate
                    best_new_board = temp_board

        if best_new_board is None or best_new_candidate is None:
            raise ValueError(f"Insufficient stock to place panel '{panel.label or '?'}'.")

        deduct_stock_usage(stock_remaining, best_new_board.width, best_new_board.length)
        best_new_board.place_candidate(idx, panel, best_new_candidate)
        boards.append(best_new_board)
        next_board_number += 1

    return boards, next_board_number


def run_optimization(request: CuttingRequest):
    if not request.panels:
        raise ValueError("At least one panel is required for optimization.")

    options = request.options
    kerf = options.kerf if options else 3.0
    consider_grain = options.consider_grain if options else False
    consider_material = options.consider_material if options else True
    use_single_sheet = options.use_single_sheet if options else False

    all_panels = expand_panels(request)
    stock_templates = build_stock_templates(request)

    validate_panels_fit(all_panels, stock_templates, kerf, consider_grain)

    if consider_material:
        grouped: Dict[Tuple, List[Tuple[int, Any]]] = defaultdict(list)
        material_lookup: Dict[Tuple, BoardSelection] = {}
        for idx, panel in all_panels:
            effective_board = panel.get_effective_board(request.board)
            sig = material_signature(effective_board)
            grouped[sig].append((idx, panel))
            material_lookup[sig] = effective_board
    else:
        sig = material_signature(request.board)
        grouped = {sig: all_panels}
        material_lookup = {sig: request.board}

    heuristics = [
        PlacementHeuristic.BEST_SHORT_SIDE_FIT,
        PlacementHeuristic.BEST_LONG_SIDE_FIT,
        PlacementHeuristic.BEST_AREA_FIT,
    ]
    sort_strategies = [
        SortStrategy.AREA_DESC,
        SortStrategy.LONGEST_SIDE_DESC,
        SortStrategy.WIDTH_DESC,
        SortStrategy.LENGTH_DESC,
        SortStrategy.PERIMETER_DESC,
    ]

    best_boards = None
    best_score = None

    for heuristic in heuristics:
        for sort_strategy in sort_strategies:
            try:
                global_stock_remaining = make_global_stock_remaining(stock_templates)
                combined_boards: List[Board] = []
                next_board_number = 1

                for sig, group_panels in grouped.items():
                    material = material_lookup[sig]
                    group_boards, next_board_number = optimize_group(
                        group_panels=group_panels,
                        group_material=material,
                        stock_templates=stock_templates,
                        stock_remaining=global_stock_remaining,
                        heuristic=heuristic,
                        sort_strategy=sort_strategy,
                        kerf=kerf,
                        consider_grain=consider_grain,
                        starting_board_number=next_board_number,
                    )
                    combined_boards.extend(group_boards)

                total_boards, total_waste, waste_percent = evaluate_boards(combined_boards)

                if use_single_sheet and total_boards > 1:
                    continue

                score = (total_boards, total_waste, waste_percent)
                if best_score is None or score < best_score:
                    best_score = score
                    best_boards = combined_boards

            except Exception as exc:
                logger.exception(
                    "Optimization attempt failed: heuristic=%s sort_strategy=%s error=%s",
                    heuristic,
                    sort_strategy,
                    exc,
                )

    if not best_boards:
        if use_single_sheet:
            raise ValueError("Unable to fit all required panels into a single sheet with current constraints.")
        raise ValueError("Unable to optimize layout with current constraints.")

    layouts: List[BoardLayout] = []
    total_panels = 0
    total_cuts = 0
    total_cut_length = 0.0

    for board in best_boards:
        cuts = generate_simple_cuts_for_board(board)
        total_cuts += len(cuts)
        total_cut_length += sum(c.length for c in cuts)
        total_panels += len(board.placed_panels)

        layouts.append(
            BoardLayout(
                board_number=board.board_number,
                board_width=board.width,
                board_length=board.length,
                used_area_mm2=board.used_area,
                waste_area_mm2=board.waste_area(),
                efficiency_percent=board.efficiency(),
                panel_count=len(board.placed_panels),
                source=board.source,
                material=material_to_dict(board.material),
                panels=board.placed_panels,
                cuts=cuts,
            )
        )

    total_boards, total_waste, total_waste_percent = evaluate_boards(best_boards)

    edging_map = defaultdict(
        lambda: {"qty": 0, "edge_per_panel_m": 0.0, "total_edge_m": 0.0, "edges_applied": "None"}
    )
    for panel in request.panels:
        edge_length_m = panel.edge_length_mm / 1000
        total_edge_m = panel.total_edge_length_mm / 1000

        edges = []
        if panel.edging.top:
            edges.append("Top")
        if panel.edging.right:
            edges.append("Right")
        if panel.edging.bottom:
            edges.append("Bottom")
        if panel.edging.left:
            edges.append("Left")

        edging_map[panel.label or "Unnamed Panel"] = {
            "qty": panel.quantity,
            "edge_per_panel_m": edge_length_m,
            "total_edge_m": total_edge_m,
            "edges_applied": ", ".join(edges) if edges else "None",
        }

    edging_details = [
        EdgingDetail(
            panel_label=label,
            quantity=values["qty"],
            edge_per_panel_m=values["edge_per_panel_m"],
            total_edge_m=values["total_edge_m"],
            edges_applied=values["edges_applied"],
        )
        for label, values in edging_map.items()
    ]

    edging_summary = EdgingSummary(
        total_meters=sum(d.total_edge_m for d in edging_details),
        details=edging_details,
    )

    optimization = OptimizationSummary(
        total_boards=total_boards,
        total_panels=total_panels,
        unique_panel_types=len(request.panels),
        total_edging_meters=edging_summary.total_meters,
        total_cuts=total_cuts,
        total_cut_length=total_cut_length,
        total_waste_mm2=total_waste,
        total_waste_percent=total_waste_percent,
        board_width=layouts[0].board_width if layouts else float(DEFAULT_BOARD_WIDTH_MM),
        board_length=layouts[0].board_length if layouts else float(DEFAULT_BOARD_LENGTH_MM),
    )

    stickers = generate_stickers(request, layouts)
    return layouts, optimization, edging_summary, stickers
