"""Central application paths and environment-backed settings."""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

FRONTEND_DIST = ROOT / "frontend" / "dist"
MODEL_CACHE = ROOT / ".models"
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://eagle_eye:eagle_eye@localhost:5432/eagle_eye",
)
CONTRACT_LIST_DEFAULT_LIMIT = 100
CONTRACT_LIST_MAX_LIMIT = 500
