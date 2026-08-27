from __future__ import annotations
import os

# Board Dimensions (Standard 4x8 ft sheet = 1220 x 2440 mm)
DEFAULT_BOARD_WIDTH_MM = 1220.0
DEFAULT_BOARD_LENGTH_MM = 2440.0

# Service Prices & Billing Rates
CUTTING_PRICE_PER_BOARD = 150.0
EDGING_PRICE_PER_METER = 50.0
CLIENT_EDGING_PRICE_PER_METER = 35.0

# Tax Configuration (0.16 = 16% VAT)
TAX_RATE = 0.16
TAX_NAME = "VAT"
CURRENCY = "KES"

# Remnant & Saw Engine Defaults
DEFAULT_KERF_MM = 3.0
DEFAULT_EDGE_THICKNESS_MM = 2.0  # PVC Edge Banding thickness
DEFAULT_TRIM_MARGIN_MM = 0.0
DEFAULT_MIN_OFFCUT_WIDTH_MM = 300.0
DEFAULT_MIN_OFFCUT_LENGTH_MM = 300.0
DEFAULT_MIN_OFFCUT_AREA_MM2 = 90000.0

# Database URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./panelpro.db")

# Branding
COMPANY_NAME = os.getenv("COMPANY_NAME", "PanelPro Factory MES")
COMPANY_LOGO_PATH = os.getenv("COMPANY_LOGO_PATH", "static/logo.png")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:5173").rstrip("/")
