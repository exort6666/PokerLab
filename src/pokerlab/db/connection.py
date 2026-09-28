from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from pokerlab.config import DB_PATH

log = logging.getLogger(__name__)

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    """Открыть соединение с БД. Создаёт папку, если её нет."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    """Контекстный менеджер: commit при успехе, rollback при ошибке."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Создать схему БД, если её нет."""
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Не найден файл схемы: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    with transaction() as conn:
        conn.executescript(schema_sql)

    log.info("Схема БД инициализирована: %s", DB_PATH)