"""HU chipEV push/fold solver — CFR+ с regret matching."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from pokerlab.mtt.cfr_pushfold import (
    ALL_HANDS, COMBOS, N_HANDS, EQ, PI_OPP, TOTAL_COMBOS,
)


RANK_ORDER = "AKQJT98765432"


def cards_to_code(cards: str) -> str | None:
    if not cards or len(cards) != 4:
        return None
    r1, s1 = cards[0], cards[1]
    r2, s2 = cards[2], cards[3]
    if r1 not in RANK_ORDER or r2 not in RANK_ORDER:
        return None
    if RANK_ORDER.index(r1) > RANK_ORDER.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        return f"{r1}{r2}"
    if s1 == s2:
        return f"{r1}{r2}s"
    return f"{r1}{r2}o"


def _sort_hands(hands: list[str]) -> list[str]:
    def key(h):
        r1 = RANK_ORDER.index(h[0])
        r2 = RANK_ORDER.index(h[1])
        if h[0] == h[1]:
            return (0, r1)
        if h.endswith("s"):
            return (1, r1, r2)
        return (2, r1, r2)
    return sorted(hands, key=key)


@dataclass
class HUSolveResult:
    pusher_start_bb: float
    caller_start_bb: float
    pusher_inv_bb: float
    caller_inv_bb: float
    dead_money_bb: float
    effective_stack_bb: float
    pot_allin_bb: float
    iterations: int = 0

    push_range: list[str] = field(default_factory=list)
    call_range: list[str] = field(default_factory=list)
    push_freq: float = 0.0
    call_freq: float = 0.0

    # EV в BB, посчитанные против сошедшейся (усреднённой) стратегии
    # оппонента. Ключи — 169 кодов рук: "AA", "AKs", "KJo", ...
    ev_push: dict[str, float] = field(default_factory=dict)
    ev_call: dict[str, float] = field(default_factory=dict)
    # Константные EV фолда (фолд-то один и тот же для всех рук):
    ev_fold_pusher: float = 0.0
    ev_fold_caller: float = 0.0


def solve_hu_chipEV(
    pusher_start_bb: float,
    caller_start_bb: float,
    pusher_inv_bb: float,
    caller_inv_bb: float,
    dead_money_bb: float,
    iterations: int = 2000,
) -> HUSolveResult:
    """
    HU chipEV push/fold CFR+.

    pusher_remaining = pusher_start − pusher_inv
    caller_remaining = caller_start − caller_inv
    E = min(pusher_remaining, caller_remaining)
    pot_allin = D + pusher_inv + caller_inv + 2E
    """
    pusher_remaining = max(0.0, pusher_start_bb - pusher_inv_bb)
    caller_remaining = max(0.0, caller_start_bb - caller_inv_bb)
    E = min(pusher_remaining, caller_remaining)
    D = dead_money_bb
    pot_allin = D + pusher_inv_bb + caller_inv_bb + 2.0 * E

    if E <= 0 or pot_allin <= 0:
        return HUSolveResult(
            pusher_start_bb=pusher_start_bb,
            caller_start_bb=caller_start_bb,
            pusher_inv_bb=pusher_inv_bb,
            caller_inv_bb=caller_inv_bb,
            dead_money_bb=dead_money_bb,
            effective_stack_bb=E,
            pot_allin_bb=pot_allin,
            ev_fold_pusher=-pusher_inv_bb,
            ev_fold_caller=-caller_inv_bb,
        )

    u_pusher_fold = -pusher_inv_bb
    u_push_caller_folds = D + caller_inv_bb
    u_caller_fold = -caller_inv_bb

    regret_p_fold = np.zeros(N_HANDS)
    regret_p_push = np.zeros(N_HANDS)
    regret_c_fold = np.zeros(N_HANDS)
    regret_c_call = np.zeros(N_HANDS)

    ss_p_push = np.zeros(N_HANDS)
    ss_c_call = np.zeros(N_HANDS)

    for t in range(1, iterations + 1):
        pos_pf = np.maximum(regret_p_fold, 0)
        pos_pp = np.maximum(regret_p_push, 0)
        total_p = pos_pf + pos_pp
        push_prob = np.where(
            total_p > 0, pos_pp / np.where(total_p > 0, total_p, 1), 0.5
        )

        pos_cf = np.maximum(regret_c_fold, 0)
        pos_cc = np.maximum(regret_c_call, 0)
        total_c = pos_cf + pos_cc
        call_prob = np.where(
            total_c > 0, pos_cc / np.where(total_c > 0, total_c, 1), 0.5
        )

        # Pusher
        W_p = PI_OPP * call_prob[None, :]
        p_call = W_p.sum(axis=1)
        eq_p_sum = (W_p * EQ).sum(axis=1)

        v_push_call = eq_p_sum * pot_allin - p_call * (pusher_inv_bb + E)
        v_push_fold = (1.0 - p_call) * u_push_caller_folds
        v_push = v_push_fold + v_push_call
        v_fold_p = np.full(N_HANDS, u_pusher_fold)
        v_pusher = push_prob * v_push + (1.0 - push_prob) * v_fold_p

        regret_p_fold = np.maximum(0.0, regret_p_fold + (v_fold_p - v_pusher))
        regret_p_push = np.maximum(0.0, regret_p_push + (v_push - v_pusher))

        # Caller
        W_c = PI_OPP * push_prob[None, :]
        p_push = W_c.sum(axis=1)
        eq_c_sum = (W_c * EQ).sum(axis=1)

        v_call = eq_c_sum * pot_allin - p_push * (caller_inv_bb + E)
        v_fold_c = np.full(N_HANDS, u_caller_fold)
        v_caller = call_prob * v_call + (1.0 - call_prob) * v_fold_c

        regret_c_fold = np.maximum(0.0, regret_c_fold + (v_fold_c - v_caller))
        regret_c_call = np.maximum(0.0, regret_c_call + (v_call - v_caller))

        ss_p_push += t * push_prob
        ss_c_call += t * call_prob

    total_weight = iterations * (iterations + 1) / 2
    avg_push_prob = ss_p_push / total_weight
    avg_call_prob = ss_c_call / total_weight

    push_arr = (avg_push_prob > 0.5).astype(np.float64)
    call_arr = (avg_call_prob > 0.5).astype(np.float64)

    push_range = [ALL_HANDS[i] for i in range(N_HANDS) if push_arr[i] > 0]
    call_range = [ALL_HANDS[i] for i in range(N_HANDS) if call_arr[i] > 0]

    push_combos = sum(COMBOS[i] for i in range(N_HANDS) if push_arr[i] > 0)
    call_combos = sum(COMBOS[i] for i in range(N_HANDS) if call_arr[i] > 0)

    # --- EV после сходимости ---
    # Пересчёт v_push / v_call против УСРЕДНЁННЫХ стратегий оппонента.
    # Это и есть EV каждой руки при игре против Nash-стратегии оппонента.
    W_p_fin = PI_OPP * avg_call_prob[None, :]
    p_call_fin = W_p_fin.sum(axis=1)
    eq_p_fin = (W_p_fin * EQ).sum(axis=1)
    v_push_final = (
        (1.0 - p_call_fin) * u_push_caller_folds
        + eq_p_fin * pot_allin
        - p_call_fin * (pusher_inv_bb + E)
    )

    W_c_fin = PI_OPP * avg_push_prob[None, :]
    p_push_fin = W_c_fin.sum(axis=1)
    eq_c_fin = (W_c_fin * EQ).sum(axis=1)
    v_call_final = eq_c_fin * pot_allin - p_push_fin * (caller_inv_bb + E)

    ev_push = {ALL_HANDS[i]: float(v_push_final[i]) for i in range(N_HANDS)}
    ev_call = {ALL_HANDS[i]: float(v_call_final[i]) for i in range(N_HANDS)}

    return HUSolveResult(
        pusher_start_bb=pusher_start_bb,
        caller_start_bb=caller_start_bb,
        pusher_inv_bb=pusher_inv_bb,
        caller_inv_bb=caller_inv_bb,
        dead_money_bb=dead_money_bb,
        effective_stack_bb=E,
        pot_allin_bb=pot_allin,
        iterations=iterations,
        push_range=_sort_hands(push_range),
        call_range=_sort_hands(call_range),
        push_freq=float(push_combos) / TOTAL_COMBOS * 100,
        call_freq=float(call_combos) / TOTAL_COMBOS * 100,
        ev_push=ev_push,
        ev_call=ev_call,
        ev_fold_pusher=float(u_pusher_fold),
        ev_fold_caller=float(u_caller_fold),
    )