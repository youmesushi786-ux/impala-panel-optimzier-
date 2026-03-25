from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfgen import canvas

from .db import SessionLocal
from .models import BoardItem, StockTransaction
from .stock_schemas import (
    BoardItemCreate,
    BoardItemUpdate,
    BoardItemOut,
    StockAdjustmentRequest,
    StockTransactionOut,
    BoardCatalogResponse,
)
from .stock_service import list_board_items, create_board_item, update_board_item, add_stock, deduct_stock, get_stock_status

router = APIRouter(prefix="/boards-admin", tags=["Boards Admin"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/", response_model=list[BoardItemOut])
def get_board_items(db: Session = Depends(get_db)):
    return list_board_items(db)


@router.get("/catalog", response_model=BoardCatalogResponse)
def get_board_catalog(db: Session = Depends(get_db)):
    return {"items": list_board_items(db)}


@router.post("/", response_model=BoardItemOut)
def create_board(payload: BoardItemCreate, db: Session = Depends(get_db)):
    return create_board_item(db, payload)


@router.patch("/{item_id}", response_model=BoardItemOut)
def patch_board(item_id: int, payload: BoardItemUpdate, db: Session = Depends(get_db)):
    item = db.query(BoardItem).filter(BoardItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")
    return update_board_item(db, item, payload)


@router.delete("/{item_id}", status_code=204)
def delete_board(item_id: int, db: Session = Depends(get_db)):
    item = db.query(BoardItem).filter(BoardItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")

    db.delete(item)
    db.commit()
    return Response(status_code=204)


@router.post("/add", response_model=BoardItemOut)
def add_board_stock(payload: StockAdjustmentRequest, db: Session = Depends(get_db)):
    item = db.query(BoardItem).filter(BoardItem.id == payload.board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")
    return add_stock(db, item, payload.quantity, payload.reference, payload.notes)


@router.post("/deduct", response_model=BoardItemOut)
def deduct_board_stock(payload: StockAdjustmentRequest, db: Session = Depends(get_db)):
    item = db.query(BoardItem).filter(BoardItem.id == payload.board_item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Board item not found")
    try:
        return deduct_stock(db, item, payload.quantity, reference=payload.reference, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/transactions/{board_item_id}", response_model=list[StockTransactionOut])
def get_transactions(board_item_id: int, db: Session = Depends(get_db)):
    return (
        db.query(StockTransaction)
        .filter(StockTransaction.board_item_id == board_item_id)
        .order_by(StockTransaction.created_at.desc())
        .all()
    )


@router.get("/print-pdf")
def print_inventory_pdf(db: Session = Depends(get_db)):
    rows = list_board_items(db)

    file_path = os.path.abspath("board_inventory.pdf")
    c = canvas.Canvas(file_path, pagesize=landscape(A4))
    page_width, page_height = landscape(A4)

    y = page_height - 30
    c.setFont("Helvetica-Bold", 14)
    c.drawString(30, y, "Board Inventory Report")
    y -= 18
    c.setFont("Helvetica", 9)
    c.drawString(30, y, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 24

    headers = ["Type", "Thk", "Color", "Company", "Width", "Length", "Price", "Qty", "Low", "Status"]
    x_positions = [30, 100, 150, 230, 330, 400, 470, 540, 590, 640]

    c.setFont("Helvetica-Bold", 9)
    for header, x in zip(headers, x_positions):
        c.drawString(x, y, header)
    y -= 18
    c.setFont("Helvetica", 8)

    for row in rows:
        if y < 40:
            c.showPage()
            y = page_height - 30

        status = get_stock_status(row.quantity, row.low_stock_threshold)
        values = [
            row.board_type,
            str(row.thickness_mm),
            row.color_name,
            row.company,
            str(int(row.width_mm)),
            str(int(row.length_mm)),
            f"{row.price_per_board:.2f}",
            str(row.quantity),
            str(row.low_stock_threshold),
            status,
        ]

        for value, x in zip(values, x_positions):
            c.drawString(x, y, str(value)[:18])

        y -= 16

    c.save()
    return FileResponse(file_path, filename="board_inventory.pdf", media_type="application/pdf")
