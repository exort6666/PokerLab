"""
CFR+ solver для push/fold HU (SB vs BB).

Counterfactual Regret Minimization Plus (Tammelin, 2014).
Гарантирует сходимость к равновесию Нэша со скоростью O(1/√T).

Reference:
- Zinkevich et al. (2007). "Regret Minimization in Games with
  Incomplete Information". NeurIPS.
- Tammelin (2014). "Solving Large Imperfect Information Games
  Using CFR+".
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

from pokerlab.core.equity_cache import equity_lookup

log = logging.getLogger(__name__)


# ============================================================
# 169 стартовых рук
# ============================================================

_RANK_CHARS = "AKQJT98765432"


def _build_all_hands() -> tuple[list[str], np.ndarray]:
    hands: list[str] = []
    combos: list[int] = []
    for i, r1 in enumerate(_RANK_CHARS):
        hands.append(f"{r1}{r1}")
        combos.append(6)
        for r2 in _RANK_CHARS[i + 1:]:
            hands.append(f"{r1}{r2}s")
            combos.append(4)
            hands.append(f"{r1}{r2}o")
            combos.append(12)
    return hands, np.array(combos, dtype=np.float64)


ALL_HANDS, COMBOS = _build_all_hands()
N_HANDS = len(ALL_HANDS)              # 169
TOTAL_COMBOS = COMBOS.sum()           # 1326
assert N_HANDS == 169 and TOTAL_COMBOS == 1326


# ============================================================
# Матрицы equity и совместимости
# ============================================================

def _build_eq_matrix() -> np.ndarray:
    eq = np.zeros((N_HANDS, N_HANDS), dtype=np.float64)
    for i, h1 in enumerate(ALL_HANDS):
        for j, h2 in enumerate(ALL_HANDS):
            eq[i, j] = equity_lookup(h1, h2)
    return eq


def _hand_to_cards(code: str) -> list[str]:
    r1, r2 = code[0], code[1]
    if r1 == r2:
        return [r1 + "h", r1 + "s"]
    if code.endswith("s"):
        return [r1 + "h", r2 + "h"]
    return [r1 + "h", r2 + "s"]


def _build_compat_matrix() -> np.ndarray:
    C = np.zeros((N_HANDS, N_HANDS), dtype=np.float64)
    for i, h1 in enumerate(ALL_HANDS):
        c1 = set(_hand_to_cards(h1))
        for j, h2 in enumerate(ALL_HANDS):
            c2 = set(_hand_to_cards(h2))
            if c1 & c2:
                C[i, j] = 0.0
            else:
                C[i, j] = COMBOS[i] * COMBOS[j]
    return C


EQ = _build_eq_matrix()
COMPAT = _build_compat_matrix()

_row_sums = COMPAT.sum(axis=1, keepdims=True)
_row_sums[_row_sums == 0] = 1.0
PI_OPP = COMPAT / _row_sums


# ============================================================
# Результат
# ============================================================

@dataclass
class CFRResult:
    stack_bb: float
    ante_bb: float
    players: int
    pot_preflop: float
    iterations: int
    exploitability: float
    push_prob: np.ndarray
    call_prob: np.ndarray
    push_range: list[str]
    call_range: list[str]


# ============================================================
# CFR+ HU chipEV
# ============================================================

def compute_pushfold_cfr(
    stack_bb: float,
    ante_bb: float = 0.0,
    players: int = 2,
    iterations: int = 20_000,
    log_every: int = 5_000,
) -> CFRResult:
    """
    Точный solver push/fold через CFR+.

    stack_bb:  эффективный стек в BB.
    ante_bb:   анте в BB (каждый платит).
    players:   число игроков (влияет на pot и анте).
    iterations: CFR+ итерации.
    """
    S = float(stack_bb)
    A = float(ante_bb)
    N = int(players)

    if N < 2:
        raise ValueError("players >= 2")

    fold_sb = -(0.5 + A)
    fold_bb = -(1.0 + A)
    push_bb_folds_sb = 1.0 + (N - 1) * A
    pot_allin = 2.0 * S + (N - 2) * A

    u_sb_push_call = EQ * pot_allin - S
    u_bb_call = (1.0 - EQ) * pot_allin - S

    regret_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    regret_bb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_bb = np.zeros((N_HANDS, 2), dtype=np.float64)

    for t in range(1, iterations + 1):
        pos_sb = np.maximum(regret_sb, 0.0)
        s_sb = pos_sb.sum(axis=1, keepdims=True)
        strategy_sb = np.where(
            s_sb > 0, pos_sb / np.where(s_sb > 0, s_sb, 1), 0.5
        )

        pos_bb = np.maximum(regret_bb, 0.0)
        s_bb = pos_bb.sum(axis=1, keepdims=True)
        strategy_bb = np.where(
            s_bb > 0, pos_bb / np.where(s_bb > 0, s_bb, 1), 0.5
        )

        # SB counterfactual values
        sigma_bb_call = strategy_bb[:, 1]
        weighted_call = PI_OPP * sigma_bb_call[None, :]
        p_call_sb = weighted_call.sum(axis=1)
        p_fold_sb = 1.0 - p_call_sb

        v_push_sb = (
            p_fold_sb * push_bb_folds_sb
            + (weighted_call * u_sb_push_call).sum(axis=1)
        )
        v_fold_sb = np.full(N_HANDS, fold_sb)

        v_strategy_sb = strategy_sb[:, 0] * v_fold_sb + strategy_sb[:, 1] * v_push_sb
        regret_sb[:, 0] = np.maximum(
            0.0, regret_sb[:, 0] + (v_fold_sb - v_strategy_sb)
        )
        regret_sb[:, 1] = np.maximum(
            0.0, regret_sb[:, 1] + (v_push_sb - v_strategy_sb)
        )

        # BB counterfactual values
        sigma_sb_push = strategy_sb[:, 1]
        weighted_push = PI_OPP * sigma_sb_push[None, :]
        p_push_bb = weighted_push.sum(axis=1)
        p_fold_bb = 1.0 - p_push_bb

        u_bb_call_T = u_bb_call.T
        v_call_bb = (
            p_fold_bb * fold_bb
            + (weighted_push * u_bb_call_T).sum(axis=1)
        )
        v_fold_bb = np.full(N_HANDS, fold_bb)

        v_strategy_bb = strategy_bb[:, 0] * v_fold_bb + strategy_bb[:, 1] * v_call_bb
        regret_bb[:, 0] = np.maximum(
            0.0, regret_bb[:, 0] + (v_fold_bb - v_strategy_bb)
        )
        regret_bb[:, 1] = np.maximum(
            0.0, regret_bb[:, 1] + (v_call_bb - v_strategy_bb)
        )

        strat_sum_sb += t * strategy_sb
        strat_sum_bb += t * strategy_bb

        if log_every and t % log_every == 0:
            log.info("CFR+ iteration %d/%d", t, iterations)

    avg_sb = strat_sum_sb / strat_sum_sb.sum(axis=1, keepdims=True)
    avg_bb = strat_sum_bb / strat_sum_bb.sum(axis=1, keepdims=True)

    push_prob = avg_sb[:, 1]
    call_prob = avg_bb[:, 1]

    exploit = _compute_exploitability(
        push_prob, call_prob, S, A, N,
        fold_sb, fold_bb, push_bb_folds_sb, pot_allin,
        u_sb_push_call, u_bb_call,
    )

    push_range = [ALL_HANDS[i] for i in range(N_HANDS) if push_prob[i] > 0.5]
    call_range = [ALL_HANDS[i] for i in range(N_HANDS) if call_prob[i] > 0.5]

    return CFRResult(
        stack_bb=S,
        ante_bb=A,
        players=N,
        pot_preflop=1.5 + N * A,
        iterations=iterations,
        exploitability=exploit,
        push_prob=push_prob,
        call_prob=call_prob,
        push_range=_sort_hands(push_range),
        call_range=_sort_hands(call_range),
    )


def _compute_exploitability(
    push_prob, call_prob, S, A, N,
    fold_sb, fold_bb, push_bb_folds_sb, pot_allin,
    u_sb_push_call, u_bb_call,
) -> float:
    sigma_bb_call = call_prob
    weighted_call = PI_OPP * sigma_bb_call[None, :]
    p_call_sb = weighted_call.sum(axis=1)
    p_fold_sb = 1.0 - p_call_sb

    v_push_sb = (
        p_fold_sb * push_bb_folds_sb
        + (weighted_call * u_sb_push_call).sum(axis=1)
    )
    v_fold_sb = np.full(N_HANDS, fold_sb)
    br_sb_value = np.maximum(v_fold_sb, v_push_sb)
    v_strategy_sb = (1 - push_prob) * v_fold_sb + push_prob * v_push_sb

    sigma_sb_push = push_prob
    weighted_push = PI_OPP * sigma_sb_push[None, :]
    p_push_bb = weighted_push.sum(axis=1)
    p_fold_bb_actual = 1.0 - p_push_bb

    u_bb_call_T = u_bb_call.T
    v_call_bb = (
        p_fold_bb_actual * fold_bb
        + (weighted_push * u_bb_call_T).sum(axis=1)
    )
    v_fold_bb = np.full(N_HANDS, fold_bb)
    br_bb_value = np.maximum(v_fold_bb, v_call_bb)
    v_strategy_bb = (1 - call_prob) * v_fold_bb + call_prob * v_call_bb

    gain_sb = (br_sb_value - v_strategy_sb).mean()
    gain_bb = (br_bb_value - v_strategy_bb).mean()
    return float(gain_sb + gain_bb)


def _sort_hands(hands: list[str]) -> list[str]:
    def key(h: str) -> tuple:
        r1 = _RANK_CHARS.index(h[0])
        r2 = _RANK_CHARS.index(h[1])
        if h[0] == h[1]:
            return (0, r1)
        if h.endswith("s"):
            return (1, r1, r2)
        return (2, r1, r2)
    return sorted(hands, key=key)


# ============================================================
# PKO HU-for-1st CFR+
# ============================================================

def compute_pushfold_pko(
    stack_bb: float,
    hero_bounty: float,
    villain_bounty: float,
    prize_1st: float = 1.0,
    prize_2nd: float = 1.0,
    own_bounty_multiplier: float = 2.0,
    iterations: int = 20_000,
) -> CFRResult:
    """
    CFR+ для HU-for-1st в PKO (Bounty Hunters).

    Правила:
      - 1-е и 2-е место получают ОДИНАКОВЫЙ приз.
      - Победитель HU забирает:
          * весь bounty оппонента (100%),
          * свой bounty × own_bounty_multiplier.
      - Проигравший получает только prize_2nd.
    """
    S = float(stack_bb)
    B_h = float(hero_bounty)
    B_v = float(villain_bounty)
    P1 = float(prize_1st)
    P2 = float(prize_2nd)
    mult = float(own_bounty_multiplier)

    def t_hero(h: float, v: float) -> float:
        if v <= 0:
            return P1 + B_v + mult * B_h
        if h <= 0:
            return P2
        x = h / (h + v)
        return x * (P1 + B_v + mult * B_h) + (1 - x) * P2

    def t_villain(h: float, v: float) -> float:
        if h <= 0:
            return P1 + B_h + mult * B_v
        if v <= 0:
            return P2
        y = v / (h + v)
        return y * (P1 + B_h + mult * B_v) + (1 - y) * P2

    u_sb_fold = t_hero(S - 0.5, S + 0.5) - P2
    u_sb_push_bbfold = t_hero(S + 1.0, S - 1.0) - P2
    u_sb_push_call_sbwin = (P1 - P2) + B_v + mult * B_h
    u_sb_push_call_bbwin = 0.0

    u_bb_push_bbfold = t_villain(S + 1.0, S - 1.0) - P2
    u_bb_push_call_bbwin = (P1 - P2) + B_h + mult * B_v
    u_bb_push_call_sbwin = 0.0

    regret_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    regret_bb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_bb = np.zeros((N_HANDS, 2), dtype=np.float64)

    for t in range(1, iterations + 1):
        pos_sb = np.maximum(regret_sb, 0.0)
        s_sb = pos_sb.sum(axis=1, keepdims=True)
        strategy_sb = np.where(
            s_sb > 0, pos_sb / np.where(s_sb > 0, s_sb, 1), 0.5
        )

        pos_bb = np.maximum(regret_bb, 0.0)
        s_bb = pos_bb.sum(axis=1, keepdims=True)
        strategy_bb = np.where(
            s_bb > 0, pos_bb / np.where(s_bb > 0, s_bb, 1), 0.5
        )

        sigma_bb_call = strategy_bb[:, 1]
        weighted_call = PI_OPP * sigma_bb_call[None, :]
        p_call_sb = weighted_call.sum(axis=1)
        p_fold_sb = 1.0 - p_call_sb

        u_call_win = (weighted_call * EQ * u_sb_push_call_sbwin).sum(axis=1)
        u_call_lose = (weighted_call * (1 - EQ) * u_sb_push_call_bbwin).sum(axis=1)

        v_push_sb = (
            p_fold_sb * u_sb_push_bbfold + u_call_win + u_call_lose
        )
        v_fold_sb = np.full(N_HANDS, u_sb_fold)

        v_strategy_sb = strategy_sb[:, 0] * v_fold_sb + strategy_sb[:, 1] * v_push_sb
        regret_sb[:, 0] = np.maximum(
            0.0, regret_sb[:, 0] + (v_fold_sb - v_strategy_sb)
        )
        regret_sb[:, 1] = np.maximum(
            0.0, regret_sb[:, 1] + (v_push_sb - v_strategy_sb)
        )

        sigma_sb_push = strategy_sb[:, 1]
        weighted_push = PI_OPP * sigma_sb_push[None, :]

        u_bb_call_matrix = (
            EQ * u_bb_push_call_sbwin + (1 - EQ) * u_bb_push_call_bbwin
        )

        v_call_bb = (weighted_push * u_bb_call_matrix.T).sum(axis=1)
        v_fold_bb = np.full(N_HANDS, u_bb_push_bbfold)

        v_strategy_bb = strategy_bb[:, 0] * v_fold_bb + strategy_bb[:, 1] * v_call_bb
        regret_bb[:, 0] = np.maximum(
            0.0, regret_bb[:, 0] + (v_fold_bb - v_strategy_bb)
        )
        regret_bb[:, 1] = np.maximum(
            0.0, regret_bb[:, 1] + (v_call_bb - v_strategy_bb)
        )

        strat_sum_sb += t * strategy_sb
        strat_sum_bb += t * strategy_bb

    avg_sb = strat_sum_sb / strat_sum_sb.sum(axis=1, keepdims=True)
    avg_bb = strat_sum_bb / strat_sum_bb.sum(axis=1, keepdims=True)

    push_prob = avg_sb[:, 1]
    call_prob = avg_bb[:, 1]

    push_range = [ALL_HANDS[i] for i in range(N_HANDS) if push_prob[i] > 0.5]
    call_range = [ALL_HANDS[i] for i in range(N_HANDS) if call_prob[i] > 0.5]

    return CFRResult(
        stack_bb=S,
        ante_bb=0.0,
        players=2,
        pot_preflop=1.5,
        iterations=iterations,
        exploitability=0.0,
        push_prob=push_prob,
        call_prob=call_prob,
        push_range=_sort_hands(push_range),
        call_range=_sort_hands(call_range),
    )
# ============================================================
# PKO HU-for-1st CFR+
# ============================================================

def compute_pushfold_pko(
    stack_bb: float,
    hero_bounty: float,
    villain_bounty: float,
    prize_1st: float = 1.0,
    prize_2nd: float = 1.0,
    own_bounty_multiplier: float = 2.0,
    iterations: int = 20_000,
) -> CFRResult:
    """
    CFR+ для HU-for-1st в PKO (Bounty Hunters).

    Правила:
      - 1-е и 2-е место получают ОДИНАКОВЫЙ приз (prize_1st == prize_2nd).
      - Победитель HU забирает:
          * весь bounty оппонента (100%),
          * свой bounty × own_bounty_multiplier.
      - Проигравший получает только prize_2nd.

    Модель "both alive":
      P(Hero wins) ≈ chip_share = h / (h + v).

    stack_bb: эффективный стек в BB.
    hero_bounty, villain_bounty: bounty ($) каждого игрока.
    own_bounty_multiplier: множитель своего bounty для победителя.
    """
    S = float(stack_bb)
    B_h = float(hero_bounty)
    B_v = float(villain_bounty)
    P1 = float(prize_1st)
    P2 = float(prize_2nd)
    mult = float(own_bounty_multiplier)

    # Хелперы t_hero, t_villain — ожидаемая выплата от состояния (h, v)
    def t_hero(h: float, v: float) -> float:
        if v <= 0:
            return P1 + B_v + mult * B_h  # Hero wins everything
        if h <= 0:
            return P2                      # Hero eliminated
        x = h / (h + v)                    # P(Hero wins) ≈ chip share
        return x * (P1 + B_v + mult * B_h) + (1 - x) * P2

    def t_villain(h: float, v: float) -> float:
        if h <= 0:
            return P1 + B_h + mult * B_v
        if v <= 0:
            return P2
        y = v / (h + v)
        return y * (P1 + B_h + mult * B_v) + (1 - y) * P2

    # Payoffs относительно baseline P2 (сдвиг на константу)
    # SB = Hero
    u_sb_fold = t_hero(S - 0.5, S + 0.5) - P2
    u_sb_push_bbfold = t_hero(S + 1.0, S - 1.0) - P2
    u_sb_push_call_sbwin = (P1 - P2) + B_v + mult * B_h
    u_sb_push_call_bbwin = 0.0

    # BB = Villain
    u_bb_push_bbfold = t_villain(S + 1.0, S - 1.0) - P2
    u_bb_push_call_bbwin = (P1 - P2) + B_h + mult * B_v
    u_bb_push_call_sbwin = 0.0

    # CFR+ arrays
    regret_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    regret_bb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_sb = np.zeros((N_HANDS, 2), dtype=np.float64)
    strat_sum_bb = np.zeros((N_HANDS, 2), dtype=np.float64)

    for t in range(1, iterations + 1):
        # Regret matching
        pos_sb = np.maximum(regret_sb, 0.0)
        s_sb = pos_sb.sum(axis=1, keepdims=True)
        strategy_sb = np.where(
            s_sb > 0, pos_sb / np.where(s_sb > 0, s_sb, 1), 0.5
        )

        pos_bb = np.maximum(regret_bb, 0.0)
        s_bb = pos_bb.sum(axis=1, keepdims=True)
        strategy_bb = np.where(
            s_bb > 0, pos_bb / np.where(s_bb > 0, s_bb, 1), 0.5
        )

        # --- SB counterfactual values ---
        sigma_bb_call = strategy_bb[:, 1]                     # (169,)
        weighted_call = PI_OPP * sigma_bb_call[None, :]       # (169, 169)
        p_call_sb = weighted_call.sum(axis=1)                 # (169,)
        p_fold_sb = 1.0 - p_call_sb

        # Слагаемое от колла BB с учётом equity
        u_call_win = (weighted_call * EQ * u_sb_push_call_sbwin).sum(axis=1)
        u_call_lose = (weighted_call * (1 - EQ) * u_sb_push_call_bbwin).sum(axis=1)

        v_push_sb = (
            p_fold_sb * u_sb_push_bbfold + u_call_win + u_call_lose
        )
        v_fold_sb = np.full(N_HANDS, u_sb_fold)

        v_strategy_sb = strategy_sb[:, 0] * v_fold_sb + strategy_sb[:, 1] * v_push_sb
        regret_sb[:, 0] = np.maximum(0.0, regret_sb[:, 0] + (v_fold_sb - v_strategy_sb))
        regret_sb[:, 1] = np.maximum(0.0, regret_sb[:, 1] + (v_push_sb - v_strategy_sb))

        # --- BB counterfactual values ---
        sigma_sb_push = strategy_sb[:, 1]                     # (169,)
        weighted_push = PI_OPP * sigma_sb_push[None, :]       # (169, 169)

        # u_bb_call[i, j] — SB hand i, BB hand j
        u_bb_call_matrix = EQ * u_bb_push_call_sbwin + (1 - EQ) * u_bb_push_call_bbwin

        # v_call[j] = sum_i PI_OPP[j, i] * sigma_sb[i] * u_bb_call[i, j]
        v_call_bb = (weighted_push * u_bb_call_matrix.T).sum(axis=1)
        v_fold_bb = np.full(N_HANDS, u_bb_push_bbfold)

        v_strategy_bb = strategy_bb[:, 0] * v_fold_bb + strategy_bb[:, 1] * v_call_bb
        regret_bb[:, 0] = np.maximum(0.0, regret_bb[:, 0] + (v_fold_bb - v_strategy_bb))
        regret_bb[:, 1] = np.maximum(0.0, regret_bb[:, 1] + (v_call_bb - v_strategy_bb))

        # Linear averaging
        strat_sum_sb += t * strategy_sb
        strat_sum_bb += t * strategy_bb

    avg_sb = strat_sum_sb / strat_sum_sb.sum(axis=1, keepdims=True)
    avg_bb = strat_sum_bb / strat_sum_bb.sum(axis=1, keepdims=True)

    push_prob = avg_sb[:, 1]
    call_prob = avg_bb[:, 1]

    push_range = [ALL_HANDS[i] for i in range(N_HANDS) if push_prob[i] > 0.5]
    call_range = [ALL_HANDS[i] for i in range(N_HANDS) if call_prob[i] > 0.5]

    return CFRResult(
        stack_bb=S,
        ante_bb=0.0,
        players=2,
        pot_preflop=1.5,
        iterations=iterations,
        exploitability=0.0,
        push_prob=push_prob,
        call_prob=call_prob,
        push_range=_sort_hands(push_range),
        call_range=_sort_hands(call_range),
    )