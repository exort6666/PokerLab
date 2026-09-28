from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = Path(os.getenv("POKERLAB_DB_PATH", PROJECT_ROOT / "data" / "pokerlab.db"))
LOG_LEVEL = os.getenv("POKERLAB_LOG_LEVEL", "INFO")
TIMEZONE = os.getenv("POKERLAB_TIMEZONE", "UTC")

DATA_DIR = PROJECT_ROOT / "data"
SAMPLE_HH_DIR = DATA_DIR / "sample_hh"