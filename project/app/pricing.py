from __future__ import annotations

from .schemas import PricingSummary, PricingLine
from .config import TAX_NAME, TAX_RATE, CURRENCY, CUTTING_PRICE_PER_BOARD, EDGING_PRICE_PER_METER


def calculate_pricing(request, optimization, edging_meters: float) -> PricingSummary:
    board_price = float(request.board.price_per_board or 0)
    board_qty = optimization.total_boards
    board_amount = board_qty * board_price

    cutting_amount = board_qty * CUTTING_PRICE_PER_BOARD
    edging_amount = edging_meters * EDGING_PRICE_PER_METER

    lines = [
        PricingLine(
            item="Boards",
            description=f"{request.board.board_type} {request.board.thickness_mm}mm {request.board.color_name} {request.board.company}",
            quantity=board_qty,
            unit="boards",
            unit_price=board_price,
            amount=board_amount,
        ),
        PricingLine(
            item="Cutting",
            description="Board cutting service",
            quantity=board_qty,
            unit="boards",
            unit_price=CUTTING_PRICE_PER_BOARD,
            amount=cutting_amount,
        ),
        PricingLine(
            item="Edging",
            description="Edge banding service",
            quantity=edging_meters,
            unit="m",
            unit_price=EDGING_PRICE_PER_METER,
            amount=edging_amount,
        ),
    ]

    subtotal = board_amount + cutting_amount + edging_amount
    tax_amount = subtotal * (TAX_RATE / 100)
    total = subtotal + tax_amount

    return PricingSummary(
        lines=lines,
        subtotal=subtotal,
        tax_name=TAX_NAME,
        tax_rate=TAX_RATE,
        tax_amount=tax_amount,
        total=total,
        currency=CURRENCY,
    )