"""
ICM (Independent Chip Model) — Malmuth-Harville.

Reference:
- Malmuth & Harville (1985).

Формула:
    P(i занимает 1-е) = s_i / S,  где S = Σ стеков
    P(i занимает k-е) = Σ_{перестановок (p1..p_{k-1}) из чужих} [
        (s_p1 / S) × (s_p2 / (S - s_p1)) × ... ×
        × (s_i / (S - s_p1 - ... - s_{k-1}))
    ]
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations


# ============================================================
# Malmuth-Harville
# ============================================================

def _permutation_prob(
    stacks: tuple[float, ...],
    placed: tuple[int, ...],
    winner: int,
) -> float:
    """
    Вероятность, что игроки из `placed` займут места 1..k в этом порядке,
    а `winner` — место k+1.

    Формула:
        s_p1 / S × s_p2 / (S - s_p1) × ... × s_winner / (S - Σ s_p)
    """
    S = sum(stacks)
    remaining_sum = S
    prob = 1.0

    for p in placed:
        if remaining_sum <= 0:
            return 0.0
        prob *= stacks[p] / remaining_sum
        remaining_sum -= stacks[p]

    if remaining_sum <= 0:
        return 0.0
    prob *= stacks[winner] / remaining_sum
    return prob


def icm_probabilities(stacks: tuple[float, ...]) -> list[list[float]]:
    """
    Возвращает матрицу P[i][k] — вероятность игрока i занять место k
    (0-indexed: k=0 — первое место).

    Для n игроков столбцы суммируются к 1 (ровно один игрок на место k).
    Строки суммируются к 1 (игрок занимает ровно одно место).
    """
    n = len(stacks)
    if n == 0:
        return []

    probs = [[0.0] * n for _ in range(n)]

    for i in range(n):
        others = [j for j in range(n) if j != i]
        for k in range(n):
            # k игроков уже заняли места 1..k, i занимает место k+1
            if k == 0:
                probs[i][0] = _permutation_prob(stacks, (), i)
                continue

            prob = 0.0
            for placed in permutations(others, k):
                prob += _permutation_prob(stacks, placed, i)
            probs[i][k] = prob

    return probs


def icm_equity(
    stacks: list[float],
    prizes: list[float],
) -> list[float]:
    """
    $EV каждого игрока по ICM.

    stacks: стеки (в любых единицах).
    prizes: призовая структура [1-е место, 2-е, ...]. Если короче n,
            оставшиеся места получают 0.

    Гарантия: sum(out) == sum(prizes).
    """
    n = len(stacks)
    if n == 0:
        return []

    probs = icm_probabilities(tuple(stacks))
    prizes_padded = list(prizes) + [0.0] * (n - len(prizes))
    prizes_padded = prizes_padded[:n]

    out: list[float] = []
    for i in range(n):
        eq = sum(probs[i][k] * prizes_padded[k] for k in range(n))
        out.append(eq)
    return out


# ============================================================
# Bubble factor
# ============================================================

@dataclass
class BubbleFactorResult:
    bf_hero: float              # bubble factor Hero
    bf_villain: float           # bubble factor Villain
    icm_call_threshold: float   # % equity для call в ICM
    chipev_threshold: float     # % equity для call в chipEV (обычно 0.5)


def bubble_factor(
    stacks: list[float],
    prizes: list[float],
    hero_idx: int,
    villain_idx: int,
    pot_bb: float,
) -> BubbleFactorResult:
    """
    Bubble factor для HU-пота Hero vs Villain.

    BF > 1 → в ICM нужен больший % эквити, чем в chipEV.
    BF < 1 → наоборот (chipEV нужен меньший).
    """
    n = len(stacks)
    equity_before = icm_equity(stacks, prizes)

    # Hero выигрывает pot
    stacks_win = stacks.copy()
    stacks_win[hero_idx] += pot_bb
    stacks_win[villain_idx] -= pot_bb
    equity_win = icm_equity(stacks_win, prizes)

    # Hero проигрывает pot
    stacks_lose = stacks.copy()
    stacks_lose[hero_idx] -= pot_bb
    stacks_lose[villain_idx] += pot_bb
    equity_lose = icm_equity(stacks_lose, prizes)

    d_win = equity_win[hero_idx] - equity_before[hero_idx]
    d_lose = equity_before[hero_idx] - equity_lose[hero_idx]

    if d_win <= 0:
        bf = float("inf")
    else:
        bf = d_lose / d_win

    # Порог: eq × d_win = (1-eq) × d_lose → eq = d_lose / (d_win + d_lose)
    icm_threshold = (
        d_lose / (d_win + d_lose) if (d_win + d_lose) > 0 else 0.5
    )

    return BubbleFactorResult(
        bf_hero=bf,
        bf_villain=1.0 / bf if bf > 0 and bf != float("inf") else 0.0,
        icm_call_threshold=icm_threshold,
        chipev_threshold=0.5,
    )