"""Добавляет таблицу hand_bounty для ручного ввода баунти."""

import sqlite3
from pathlib import Path

schema_add = """
CREATE TABLE IF NOT EXISTS hand_bounty (
    hand_id         TEXT PRIMARY KEY REFERENCES hands(id) ON DELETE CASCADE,
    hero_bounty     REAL NOT NULL DEFAULT 0,
    villain_bounty  REAL NOT NULL DEFAULT 0,
    source          TEXT NOT NULL DEFAULT 'manual',
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

conn = sqlite3.connect("data/pokerlab.db")
conn.executescript(schema_add)
conn.commit()
conn.close()
print("OK: hand_bounty created")