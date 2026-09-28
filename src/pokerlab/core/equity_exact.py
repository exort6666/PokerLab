"""
Точный equity для двух рук через полный перебор бордов.

Использует phevaluator — 100% точность, никакой Monte Carlo.
"""

from __future__ import annotations

from itertools import combinations

from pokerlab.core.cards import Card, Suit, ALL_CARDS
from pokerlab.core.evaluator import evaluate


def _remaining_deck(used: list[Card]) -> list[Card]:
    used_set = set(used)
    return [c for c in ALL_CARDS if c not in used_set]


def equity_exact(
    hero: list[Card],
    villain: list[Card],
    board: list[Card] | None = None,
) -> float:
    """
    Точный equity Hero против Villain.
    Перебирает ВСЕ возможные борды.

    hero, villain: по 2 карты.
    board: 0, 3, 4 или 5 карт.

    Возвращает долю Hero (0.0 .. 1.0). Точность — 100%.
    """
    if board is None:
        board = []
    if len(hero) != 2 or len(villain) != 2:
        raise ValueError("hero и villain должны иметь по 2 карты")
    if len(board) not in (0, 3, 4, 5):
        raise ValueError("board: 0, 3, 4 или 5 карт")

    used = hero + villain + board
    if len(set(used)) != len(used):
        raise ValueError("Дубликат карты")

    deck = _remaining_deck(used)
    need = 5 - len(board)

    total = 0.0
    count = 0

    # Перебираем все борды
    if need == 0:
        hero_score = evaluate(hero + board)
        villain_score = evaluate(villain + board)
        if hero_score > villain_score:
            return 1.0
        if hero_score < villain_score:
            return 0.0
        return 0.5

    for extra in combinations(deck, need):
        full_board = board + list(extra)
        hero_score = evaluate(hero + full_board)
        villain_score = evaluate(villain + full_board)
        if hero_score > villain_score:
            total += 1.0
        elif hero_score < villain_score:
            total += 0.0
        else:
            total += 0.5
        count += 1

    return total / count