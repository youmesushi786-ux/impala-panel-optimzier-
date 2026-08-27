from __future__ import annotations

import logging
from app.db import engine, SessionLocal, Base
from app.models import BoardItem

logger = logging.getLogger("panelpro")


def seed_default_stock(db):
    """Seed standard 1220x2440 mm industrial catalog sheets if DB is empty."""
    if db.query(BoardItem).count() > 0:
        return

    default_boards = [
        BoardItem(board_type="MDF", thickness_mm=18.0, color_name="Oxford Cherry", company="Complywood", width_mm=1220, length_mm=2440, price_per_board=3400.0, quantity=40),
        BoardItem(board_type="MDF", thickness_mm=18.0, color_name="White Matt", company="Complywood", width_mm=1220, length_mm=2440, price_per_board=3400.0, quantity=50),
        BoardItem(board_type="MDF", thickness_mm=18.0, color_name="African Mahogany", company="Complywood", width_mm=1220, length_mm=2440, price_per_board=3400.0, quantity=30),
        BoardItem(board_type="Particleboard", thickness_mm=18.0, color_name="White", company="Generic", width_mm=1220, length_mm=2440, price_per_board=3200.0, quantity=25),
        BoardItem(board_type="Plywood", thickness_mm=18.0, color_name="Raw Unfaced", company="Generic", width_mm=1220, length_mm=2440, price_per_board=4200.0, quantity=20),
    ]
    db.add_all(default_boards)
    db.commit()
    logger.info("Seeded default factory stock catalog into database.")


def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_default_stock(db)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    print("Database tables initialized and catalog seeded successfully.")
