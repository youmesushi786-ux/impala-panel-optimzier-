from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import asc

from .models import BoardItem, StockTransaction


def get_stock_status(quantity: int, low_stock_threshold: int) -> str:
    if quantity <= 0:
        return "out_of_stock"
    if quantity <= low_stock_threshold:
        return "low_stock"
    return "in_stock"


def list_board_items(db: Session):
    return (
        db.query(BoardItem)
        .order_by(
            asc(BoardItem.board_type),
            asc(BoardItem.thickness_mm),
            asc(BoardItem.company),
            asc(BoardItem.color_name),
        )
        .all()
    )


def create_board_item(db: Session, data):
    item = BoardItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)

    tx = StockTransaction(
        board_item_id=item.id,
        transaction_type="add",
        quantity=item.quantity,
        balance_before=0,
        balance_after=item.quantity,
        reference="INITIAL_STOCK",
        notes="Initial stock entry",
    )
    db.add(tx)
    db.commit()

    return item


def update_board_item(db: Session, item: BoardItem, data):
    old_quantity = item.quantity
    payload = data.model_dump(exclude_unset=True)

    for key, value in payload.items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)

    if "quantity" in payload and payload["quantity"] != old_quantity:
        tx = StockTransaction(
            board_item_id=item.id,
            transaction_type="adjust",
            quantity=payload["quantity"] - old_quantity,
            balance_before=old_quantity,
            balance_after=payload["quantity"],
            reference="MANUAL_ADJUSTMENT",
            notes="Quantity adjusted manually by admin",
        )
        db.add(tx)
        db.commit()

    return item


def add_stock(db: Session, item: BoardItem, quantity: int, reference: str | None = None, notes: str | None = None):
    before = item.quantity
    after = before + quantity
    item.quantity = after
    db.commit()
    db.refresh(item)

    tx = StockTransaction(
        board_item_id=item.id,
        transaction_type="add",
        quantity=quantity,
        balance_before=before,
        balance_after=after,
        reference=reference,
        notes=notes,
    )
    db.add(tx)
    db.commit()
    return item


def deduct_stock(db: Session, item: BoardItem, quantity: int, report_id: str | None = None, reference: str | None = None, notes: str | None = None):
    if item.quantity < quantity:
        raise ValueError(f"Insufficient stock for board item {item.id}")

    before = item.quantity
    after = before - quantity
    item.quantity = after
    db.commit()
    db.refresh(item)

    tx = StockTransaction(
        board_item_id=item.id,
        transaction_type="deduct",
        quantity=quantity,
        balance_before=before,
        balance_after=after,
        report_id=report_id,
        reference=reference,
        notes=notes,
    )
    db.add(tx)
    db.commit()
    return item