from __future__ import annotations

import os

DEFAULT_BOARD_WIDTH_MM = 1220
DEFAULT_BOARD_LENGTH_MM = 2440

CUTTING_PRICE_PER_BOARD = 150
EDGING_PRICE_PER_METER = 50
TAX_RATE = 16.0
TAX_NAME = "VAT"
CURRENCY = "KES"

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

COMPANY_NAME = os.getenv("COMPANY_NAME", "PanelPro")
COMPANY_LOGO_PATH = os.getenv("COMPANY_LOGO_PATH", "static/logo.png")