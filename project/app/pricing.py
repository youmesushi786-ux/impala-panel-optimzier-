from __future__ import annotations

from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER, TAX_RATE, TAX_NAME
from app.schemas import CuttingRequest, OptimizationSummary, PricingLine, PricingBreakdown


def calculate_pricing(
    request: CuttingRequest,
    optimization: OptimizationSummary,
    total_edging_meters: float,
) -> PricingBreakdown:
    lines = []

    # 1. Full-sheet raw material cost
    full_sheets_count = getattr(optimization, "total_full_sheets", optimization.total_boards)
    board_cost = full_sheets_count * request.board.price_per_board
    if full_sheets_count > 0:
        lines.append(
            PricingLine(
                item="Full Boards",
                description=f"{full_sheets_count}x {request.board.board_type} {request.board.color_name} ({request.board.company})",
                quantity=float(full_sheets_count),
                unit_price=request.board.price_per_board,
                amount=round(board_cost, 2),
            )
        )

    # 2. Offcut material (Discounted / Reused from workshop pool)
    offcuts_count = getattr(optimization, "total_offcuts_used", 0)
    if offcuts_count > 0:
        offcut_unit_price = request.board.price_per_board * 0.4  # 60% remnant discount
        offcut_cost = offcuts_count * offcut_unit_price
        lines.append(
            PricingLine(
                item="Reused Remnants",
                description=f"{offcuts_count}x Workshop Offcut(s) [Discounted]",
                quantity=float(offcuts_count),
                unit_price=offcut_unit_price,
                amount=round(offcut_cost, 2),
            )
        )

    # 3. Cutting labor fee
    total_boards = optimization.total_boards
    cutting_cost = total_boards * CUTTING_PRICE_PER_BOARD
    lines.append(
        PricingLine(
            item="Cutting Labor",
            description=f"Cutting labor for {total_boards} board(s)",
            quantity=float(total_boards),
            unit_price=CUTTING_PRICE_PER_BOARD,
            amount=round(cutting_cost, 2),
        )
    )

    # 4. Edge-banding application fee
    edging_cost = total_edging_meters * EDGING_PRICE_PER_METER
    lines.append(
        PricingLine(
            item="Edge Banding",
            description=f"{total_edging_meters:.2f} m PVC edge application",
            quantity=total_edging_meters,
            unit_price=EDGING_PRICE_PER_METER,
            amount=round(edging_cost, 2),
        )
    )

    subtotal = round(sum(ln.amount for ln in lines), 2)
    tax = round(subtotal * TAX_RATE, 2)  # Correct TAX_RATE fraction (0.16)
    total = round(subtotal + tax, 2)

    return PricingBreakdown(lines=lines, subtotal=subtotal, tax=tax, total=total)
