from app.config import CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER, TAX_RATE
from app.schemas import CuttingRequest, OptimizationSummary, PricingLine, PricingSummary


def calculate_pricing(
    request: CuttingRequest,
    optimization: OptimizationSummary,
    total_edging_meters: float,
) -> PricingSummary:
    lines = []

    # 1. Board material
    board_cost = optimization.total_boards * request.board.price_per_board
    lines.append(
        PricingLine(
            item="Boards",
            description=(
                f"{optimization.total_boards}x "
                f"{request.board.board_type} {request.board.color_name}"
            ),
            quantity=float(optimization.total_boards),
            unit_price=request.board.price_per_board,
            amount=round(board_cost, 2),
        )
    )

    # 2. Cutting
    cutting_cost = optimization.total_boards * CUTTING_PRICE_PER_BOARD
    lines.append(
        PricingLine(
            item="Cutting",
            description=f"Cutting {optimization.total_boards} board(s)",
            quantity=float(optimization.total_boards),
            unit_price=CUTTING_PRICE_PER_BOARD,
            amount=round(cutting_cost, 2),
        )
    )

    # 3. Edging
    edging_cost = total_edging_meters * EDGING_PRICE_PER_METER
    lines.append(
        PricingLine(
            item="Edging",
            description=f"{total_edging_meters:.2f} m edge-banding",
            quantity=total_edging_meters,
            unit_price=EDGING_PRICE_PER_METER,
            amount=round(edging_cost, 2),
        )
    )

    subtotal = round(sum(ln.amount for ln in lines), 2)
    tax = round(subtotal * TAX_RATE, 2)
    total = round(subtotal + tax, 2)

    return PricingSummary(lines=lines, subtotal=subtotal, tax=tax, total=total)
