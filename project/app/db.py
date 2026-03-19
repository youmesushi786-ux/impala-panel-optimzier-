from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------
# Database URL
# ---------------------------------------------------------
# Priority:
# 1. DATABASE_URL from environment
# 2. fallback to local sqlite database
# ---------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")

# ---------------------------------------------------------
# Engine
# ---------------------------------------------------------

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(DATABASE_URL)

# ---------------------------------------------------------
# Session factory
# ---------------------------------------------------------

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)