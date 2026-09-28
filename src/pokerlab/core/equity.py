from __future__ import annotations

from collections.abc import Iterable

from pokerlab.core.cards import Card
from pokerlab.core.equity_exact import equity_exact


def equity(
    hero: list[Card],
    villain: list[Card],
    board: list[Card] | None = None,
    iterations: int = 10_000,   # игнорируется
    seed: int | None = None,    # игнорируется
) -> float:
    """
    Точный equity Hero vs Villain.

    Параметры iterations и seed оставлены для обратной совместимости,
    но не используются — считаем точно через перебор.
    """
    return equity_exact(hero, villain, board)