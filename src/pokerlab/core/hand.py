"""
Оценка покерных рук (5–7 карт).

Возвращает числовой рейтинг: чем больше, тем сильнее.
Одинаковые рейтинги = одинаковые руки.

Категории (снизу вверх):
  0: High card
  1: Pair
  2: Two pair
  3: Three of a kind
  4: Straight
  5: Flush
  6: Full house
  7: Four of a kind
  8: Straight flush
  9: Royal flush (частный случай straight flush)
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

from pokerlab.core.cards import Card

# Ранги для оценки (2..14)
_RANKS = list(range(2, 15))


def _rank_counts(cards: Iterable[Card]) -> dict[int, int]:
    """{ранг: количество} для переданных карт."""
    counts: dict[int, int] = {}
    for c in cards:
        counts[c.rank] = counts.get(c.rank, 0) + 1
    return counts


def _is_straight(ranks: list[int]) -> tuple[bool, int]:
    """
    Проверить стрит.
    Возвращает (True, старший_ранг_стрита) или (False, 0).
    Учитывает A-2-3-4-5 (колесо), где старший ранг = 5.
    """
    s = set(ranks)
    # Обычный стрит
    for high in range(14, 4, -1):
        if all(r in s for r in range(high - 4, high + 1)):
            return True, high
    # Колесо A-2-3-4-5
    if {14, 2, 3, 4, 5}.issubset(s):
        return True, 5
    return False, 0


def _is_flush(cards: list[Card]) -> bool:
    """Проверить, что все 5 карт одной масти."""
    return len({c.suit for c in cards}) == 1


def _evaluate_five(cards: list[Card]) -> tuple[int, tuple[int, ...]]:
    """
    Оценить ровно 5 карт.
    Возвращает (category, tiebreakers).
    tiebreakers — кортеж рангов для сравнения рук одной категории.
    """
    assert len(cards) == 5

    ranks = sorted((c.rank for c in cards), reverse=True)
    counts = _rank_counts(cards)

    # Сортированные ранги по (частота, ранг) — для сравнения
    by_count = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    sorted_by_count = [r for r, _ in by_count]

    is_flush = _is_flush(cards)
    is_straight, straight_high = _is_straight(ranks)

    # Straight flush
    if is_flush and is_straight:
        return 8, (straight_high,)

    # Four of a kind
    if by_count[0][1] == 4:
        quad_rank = by_count[0][0]
        kicker = max(r for r in ranks if r != quad_rank)
        return 7, (quad_rank, kicker)

    # Full house
    if by_count[0][1] == 3 and by_count[1][1] >= 2:
        return 6, (by_count[0][0], by_count[1][0])

    # Flush
    if is_flush:
        return 5, tuple(ranks)

    # Straight
    if is_straight:
        return 4, (straight_high,)

    # Three of a kind
    if by_count[0][1] == 3:
        trips = by_count[0][0]
        kickers = sorted((r for r in ranks if r != trips), reverse=True)[:2]
        return 3, (trips, *kickers)

    # Two pair
    if by_count[0][1] == 2 and by_count[1][1] == 2:
        high_pair = max(by_count[0][0], by_count[1][0])
        low_pair = min(by_count[0][0], by_count[1][0])
        kicker = max(r for r in ranks if r not in (high_pair, low_pair))
        return 2, (high_pair, low_pair, kicker)

    # One pair
    if by_count[0][1] == 2:
        pair = by_count[0][0]
        kickers = sorted((r for r in ranks if r != pair), reverse=True)[:3]
        return 1, (pair, *kickers)

    # High card
    return 0, tuple(ranks)


def evaluate(cards: list[Card]) -> tuple[int, tuple[int, ...]]:
    """
    Оценить 5–7 карт. Возвращает лучшую комбинацию.
    Для 5 карт — просто _evaluate_five.
    Для 6–7 — перебираем все 5-карточные подмножества.
    """
    if len(cards) < 5:
        raise ValueError(f"Нужно 5–7 карт, получено {len(cards)}")
    if len(cards) == 5:
        return _evaluate_five(cards)

    best: tuple[int, tuple[int, ...]] | None = None
    for combo in combinations(cards, 5):
        result = _evaluate_five(list(combo))
        if best is None or result > best:
            best = result
    assert best is not None
    return best