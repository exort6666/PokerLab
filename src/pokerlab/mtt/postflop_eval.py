"""
Быстрый evaluator для постфлопа с кэшем.

Fix v2: canonical_cards принимает board и выбирает карты класса
        так, чтобы не конфликтовать с ним. Иначе phevaluator получает
        дубликаты и выдаёт мусор (или падает).
"""

from __future__ import annotations

from functools import lru_cache

from phevaluator import evaluate_cards


_RANKS = "AKQJT98765432"
_SUITS = "shdc"


# ============================================================
# Базовый API
# ============================================================

def rank(cards: list[str]) -> int:
    return evaluate_cards(*cards)


@lru_cache(maxsize=500_000)
def rank_key(cards_key: str) -> int:
    cards = [cards_key[i:i + 2] for i in range(0, len(cards_key), 2)]
    return evaluate_cards(*cards)


def rank_fast(hand: list[str], board: list[str]) -> int:
    key = "".join(sorted(hand + board))
    return rank_key(key)


# ============================================================
# Карты для 169-класса с учётом борда
# ============================================================

def canonical_cards(hand_code: str,
                    board: list[str] | None = None) -> list[str]:
    """
    Конкретные 2 карты для класса (например 'AKs', 'QQ', 'AKo').

    Если задан board — исключаем карты, которые уже на борде.
    Для каждого класса всегда есть валидная пара:
        пары (6 комбо, 4 масти) — берём 2 разные масти, не на борде;
        suited (4 комбо, 4 масти) — берём масть, где ни одна карта
            не на борде;
        offsuit (12 комбо) — берём 2 разных масти, обе карты не на борде.
    """
    if board is None:
        board = []
    board_set = set(board)

    r1, r2 = hand_code[0], hand_code[1]

    if r1 == r2:
        # Пара — берём первые две масти, где нет коллизий
        for s1 in _SUITS:
            if r1 + s1 in board_set:
                continue
            for s2 in _SUITS:
                if s2 == s1:
                    continue
                if r1 + s2 in board_set:
                    continue
                return [r1 + s1, r1 + s2]
        # Все 4 масти заблокированы — теоретически невозможно
        # (4 карты на борде максимум 4, но они должны быть разных мастей)
        raise ValueError(f"Нет валидных карт для {hand_code}")

    if hand_code.endswith("s"):
        # Suited — одна масть для обеих карт
        for s in _SUITS:
            if r1 + s in board_set:
                continue
            if r2 + s in board_set:
                continue
            return [r1 + s, r2 + s]
        # Флеш-масти заблокированы — fallback: играем offsuit-вариант
        # (крайне редко, только когда на борде 4+ одной масти)
        return _fallback_offsuit(r1, r2, board_set)

    # Offsuit — две разные масти
    for s1 in _SUITS:
        if r1 + s1 in board_set:
            continue
        for s2 in _SUITS:
            if s2 == s1:
                continue
            if r2 + s2 in board_set:
                continue
            return [r1 + s1, r2 + s2]

    raise ValueError(f"Нет валидных карт для {hand_code}")


def _fallback_offsuit(r1: str, r2: str,
                       board_set: set[str]) -> list[str]:
    for s1 in _SUITS:
        if r1 + s1 in board_set:
            continue
        for s2 in _SUITS:
            if s2 == s1:
                continue
            if r2 + s2 in board_set:
                continue
            return [r1 + s1, r2 + s2]
    raise ValueError(f"Нет валидных карт для {r1}{r2}o "
                     f"(все масти заблокированы)")


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    import time

    # Корректность: без коллизий на борде
    board = ["As", "Ks", "Qs"]
    for h in ["AA", "AKs", "AKo", "AQs", "AQo", "72o", "22", "KQo"]:
        cards = canonical_cards(h, board)
        assert not (set(cards) & set(board)), \
            f"Коллизия для {h}: {cards} vs {board}"
        r = rank_fast(cards, board)
        print(f"{h:>4} → {cards} → rank={r}")

    print()

    # Скорость
    hand = ["As", "Ks"]
    board = ["Qs", "Js", "Ts"]
    t0 = time.time()
    n = 50_000
    for _ in range(n):
        rank_fast(hand, board)
    elapsed = time.time() - t0
    print(f"{n} оценок за {elapsed:.3f} сек "
          f"({n/elapsed:,.0f} оценок/сек)")
    print(f"Кэш: {rank_key.cache_info()}")