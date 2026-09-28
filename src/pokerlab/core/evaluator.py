"""
Обёртка над phevaluator — точный 5/7-карточный evaluator.

phevaluator использует ту же combinadic-based lookup table, что
PokerStove. Точность — 100%.

Конвенция phevaluator: чем МЕНЬШЕ rank, тем СИЛЬНЕЕ рука.
В нашем проекте (core/hand.py) было наоборот. Здесь приводим
к нашему стилю: больше = сильнее.
"""

from __future__ import annotations

from phevaluator import evaluate_cards


def evaluate(cards: list) -> int:
    """
    Оценить 5–7 карт. Возвращает СИЛУ руки (больше = сильнее).

    cards: список объектов Card из core.cards.
    """
    # Card имеет rank 2..14 и suit 0..3
    # phevaluator ожидает строки вида 'Ah', 'Ks', '2c'
    _RANK_CHARS = "23456789TJQKA"
    _SUIT_CHARS = "cdhs"

    strs = [
        _RANK_CHARS[c.rank - 2] + _SUIT_CHARS[int(c.suit)]
        for c in cards
    ]
    # phevaluator: чем меньше — тем сильнее. Инвертируем.
    return 1_000_000 - evaluate_cards(*strs)