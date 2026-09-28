"""
ChipEV push/fold для heads-up спота (SB vs BB).

Ищет равновесие Нэша:
- SB пушит диапазон, где EV(push) > EV(fold) = -0.5 BB.
- BB коллит диапазон, где EV(call) > EV(fold) = -1.0 BB.

Использует предпосчитанную таблицу preflop equity — расчёт мгновенный.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pokerlab.core.equity_cache import equity_lookup


# ============================================================
# Все 169 стартовых рук с количеством комбо
# ============================================================

_RANK_CHARS = "AKQJT98765432"


def _build_hands() -> dict[str, int]:
    """{код руки: количество комбо}."""
    hands: dict[str, int] = {}
    for i, r1 in enumerate(_RANK_CHARS):
        # Пары: 6 комбо
        hands[f"{r1}{r1}"] = 6
        # Suited: 4 комбо, Offsuit: 12 комбо
        for r2 in _RANK_CHARS[i + 1:]:
            hands[f"{r1}{r2}s"] = 4
            hands[f"{r1}{r2}o"] = 12
    return hands


ALL_HANDS: dict[str, int] = _build_hands()
TOTAL_COMBOS: int = sum(ALL_HANDS.values())  # 1326
assert len(ALL_HANDS) == 169
assert TOTAL_COMBOS == 1326


# ============================================================
# Результат
# ============================================================

@dataclass
class PushFoldResult:
    stack_bb: float
    ante_bb: float
    players: int
    pot_preflop: float

    push_range: list[str] = field(default_factory=list)
    push_combos: int = 0
    push_freq: float = 0.0  # % от всех комбо

    call_range: list[str] = field(default_factory=list)
    call_combos: int = 0
    call_freq: float = 0.0

    iterations_run: int = 0


# ============================================================
# Расчёт
# ============================================================

def compute_pushfold_hu(
    stack_bb: float,
    ante_bb: float = 0.0,
    players: int = 8,
    iterations: int = 200,
    avg_window: int = 50,
) -> PushFoldResult:
    """
    Найти равновесие push/fold для heads-up (SB vs BB).

    Использует iterated best response + усреднение последних итераций.
    Это даёт аппроксимацию Нэша (смешанная стратегия).
    """
    from collections import Counter

    antes_total = ante_bb * players
    pot_preflop = 1.5 + antes_total

    needed_eq_bb = (stack_bb - 1.0) / (2.0 * stack_bb + antes_total)

    push_range: set[str] = set(ALL_HANDS.keys())
    call_range: set[str] = set(ALL_HANDS.keys())

    push_history: list[frozenset[str]] = []
    call_history: list[frozenset[str]] = []

    for _ in range(iterations):
        # --- BB: best response call против текущего push_range ---
        sb_combos = sum(ALL_HANDS[h] for h in push_range)
        new_call: set[str] = set()
        if sb_combos > 0:
            for h_bb in ALL_HANDS:
                eq_sum = 0.0
                for h_sb in push_range:
                    eq_sum += ALL_HANDS[h_sb] * equity_lookup(h_bb, h_sb)
                avg_eq = eq_sum / sb_combos
                if avg_eq > needed_eq_bb:
                    new_call.add(h_bb)
        call_range = new_call

        # --- SB: best response push против текущего call_range ---
        bb_combos = sum(ALL_HANDS[h] for h in call_range)
        p_fold = 1.0 - bb_combos / TOTAL_COMBOS
        new_push: set[str] = set()
        for h_sb in ALL_HANDS:
            if bb_combos > 0:
                eq_sum = 0.0
                for h_bb in call_range:
                    eq_sum += ALL_HANDS[h_bb] * equity_lookup(h_sb, h_bb)
                eq_vs_call = eq_sum / bb_combos
            else:
                eq_vs_call = 1.0
            ev_push = (
                p_fold * (1.0 + antes_total)
                + (1.0 - p_fold) * (
                    eq_vs_call * (2.0 * stack_bb + antes_total) - stack_bb
                )
            )
            if ev_push > -0.5:
                new_push.add(h_sb)
        push_range = new_push

        push_history.append(frozenset(push_range))
        call_history.append(frozenset(call_range))

    # --- Проверка сходимости ---
    recent_push = push_history[-avg_window:]
    recent_call = call_history[-avg_window:]

    if len(set(recent_push)) == 1 and len(set(recent_call)) == 1:
        final_push = recent_push[-1]
        final_call = recent_call[-1]
    else:
        # Осцилляция: усредняем
        push_counts: Counter = Counter()
        for s in recent_push:
            push_counts.update(s)
        call_counts: Counter = Counter()
        for s in recent_call:
            call_counts.update(s)

        threshold = avg_window * 0.4
        final_push = frozenset(
            h for h, c in push_counts.items() if c >= threshold
        )
        final_call = frozenset(
            h for h, c in call_counts.items() if c >= threshold
        )

    push_combos = sum(ALL_HANDS[h] for h in final_push)
    call_combos = sum(ALL_HANDS[h] for h in final_call)

    return PushFoldResult(
        stack_bb=stack_bb,
        ante_bb=ante_bb,
        players=players,
        pot_preflop=pot_preflop,
        push_range=_sort_hands(set(final_push)),
        push_combos=push_combos,
        push_freq=push_combos / TOTAL_COMBOS * 100,
        call_range=_sort_hands(set(final_call)),
        call_combos=call_combos,
        call_freq=call_combos / TOTAL_COMBOS * 100,
        iterations_run=iterations,
    )

def _sort_hands(hands: set[str]) -> list[str]:
    """Сортировка рук: пары → suited → offsuit, по убыванию ранга."""
    def key(h: str) -> tuple:
        r1 = _RANK_CHARS.index(h[0])
        r2 = _RANK_CHARS.index(h[1])
        is_pair = h[0] == h[1]
        is_suited = h.endswith("s")
        # Пара: (0, r1), Suited: (1, r1, r2), Offsuit: (2, r1, r2)
        if is_pair:
            return (0, r1)
        if is_suited:
            return (1, r1, r2)
        return (2, r1, r2)

    return sorted(hands, key=key)