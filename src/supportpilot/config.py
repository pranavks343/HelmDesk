"""Environment loading, filesystem paths and project-wide constants."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
KB_DIR = DATA_DIR / "kb"
CRM_PATH = DATA_DIR / "crm.json"
KB_SOURCES = ("docs", "forum", "changelog")

DEFAULT_RECURSION_LIMIT = 25
SUPERVISOR_MAX_HOPS = 4
SUPERVISOR_MIN_REMAINING = 6
ROUTE_CONFIDENCE_FLOOR = 0.5
REWRITE_LIMIT = 2


def ledger_path() -> Path:
    """Refund ledger location (env-overridable so tests never touch real data)."""
    return Path(os.environ.get("SUPPORTPILOT_LEDGER", DATA_DIR / "refund_ledger.json"))


def db_path() -> str:
    return os.environ.get("SUPPORTPILOT_DB", str(ROOT / "supportpilot.db"))


def store_db_path() -> str:
    return os.environ.get("SUPPORTPILOT_STORE_DB", str(ROOT / "supportpilot_store.db"))


def default_provider() -> str:
    return os.environ.get("SUPPORTPILOT_LLM", "fake")


def default_model() -> str:
    return os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
