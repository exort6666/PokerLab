"""
Загрузка предпосчитанной preflop equity таблицы.

Таблица содержит equity для всех пар стартовых рук (169×169).
Ключи в JSON: 'AA|KK' → 0.8231 (equity AA против KK).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from pokerlab.config import PROJECT_ROOT


EQUITY_PATH = PROJECT_ROOT / "data" / "preflop_equity.json"


@lru_cache(maxsize=1)
def _load_table() -> dict[str, float]:
    """Загрузить таблицу один раз и закешировать в памяти."""
    if not EQUITY_PATH.exists():
        raise FileNotFoundError(
            f"Не найдена таблица equity: {EQUITY_PATH}\n"
            f"Запусти: python tools/precompute_equity.py"
        )
    with EQUITY_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def equity_lookup(h1: str, h2: str) -> float:
    """
    Equity руки h1 против h2.
    h1, h2 — коды рук: 'AA', 'AKs', 'AKo'.

    Использует симметрию: eq(A, B) = 1 - eq(B, A).
    """
    table = _load_table()
    key = f"{h1}|{h2}"
    if key in table:
        return table[key]
    rev = f"{h2}|{h1}"
    if rev in table:
        return 1.0 - table[rev]
    raise KeyError(f"Нет equity для {h1} vs {h2}")