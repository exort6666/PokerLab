"""
Bounty-ICM (PKO — Progressive Knockout).

Модель GGPoker:
- Каждый игрок несёт bounty B_i.
- При нокауте j победитель i получает B_j / 2 в кэш,
  B_j / 2 добавляется к его bounty.
- Порядок вылетов по Malmuth-Harville.

Reference:
- PKO механика GGPoker.
- Адаптация Malmuth-Harville (1985).
"""

from __future__ import annotations

import random
from dataclasses import dataclass


def bounty_icm_equity(
    stacks: list[float],
    bounties: list[float],
    prizes: list[float],
    n_simulations: int = 5000,
    seed: int = 42,
) -> list[float]:
    """
    $EV каждого игрока с учётом ICM (prizes) и bounty (PKO).

    Симуляция:
    1. Порядок вылетов по Malmuth-Harville (order[0] = победитель).
    2. Для каждого вылета j (кроме победителя) случайный живой i
       получает B_j / 2.
    """
    n = len(stacks)
    if n == 0:
        return []
    if n == 1:
        return [sum(prizes)]

    rng = random.Random(seed)
    prizes_padded = list(prizes) + [0.0] * max(0, n - len(prizes))
    prizes_padded = prizes_padded[:n]

    ev_prize = [0.0] * n
    ev_bounty = [0.0] * n

    for _ in range(n_simulations):
        # Порядок вылетов по MH
        remaining = list(range(n))
        order: list[int] = []
        while remaining:
            total = sum(stacks[i] for i in remaining)
            if total <= 0:
                order.extend(remaining)
                break
            r = rng.uniform(0, total)
            cum = 0.0
            chosen = remaining[-1]
            for i in remaining:
                cum += stacks[i]
                if cum >= r:
                    chosen = i
                    break
            order.append(chosen)
            remaining.remove(chosen)

        # Призовые
        for k, i in enumerate(order):
            ev_prize[i] += prizes_padded[k]

        # Нокауты: order[n-1] — первый вылетевший
        for idx in range(n - 1, 0, -1):
            j = order[idx]
            alive = order[:idx]
            total_alive = sum(stacks[i] for i in alive)
            if total_alive <= 0:
                continue
            r = rng.uniform(0, total_alive)
            cum = 0.0
            killer = alive[-1]
            for i in alive:
                cum += stacks[i]
                if cum >= r:
                    killer = i
                    break
            ev_bounty[killer] += bounties[j] / 2

    return [
        (ev_prize[i] + ev_bounty[i]) / n_simulations
        for i in range(n)
    ]


@dataclass
class BountyBFResult:
    bf_hero: float
    icm_threshold: float
    ev_current: float
    ev_win: float
    ev_lose: float


def bounty_bubble_factor(
    stacks: list[float],
    bounties: list[float],
    prizes: list[float],
    hero_idx: int,
    villain_idx: int,
    pot_bb: float,
    n_simulations: int = 2000,
    seed: int = 42,
) -> BountyBFResult:
    """
    Bubble factor с учётом PKO (progressive knockout).

    При нокауте Villain:
    - Hero получает B_v / 2 в кэш.
    - Hero's bounty растёт на B_v / 2 (ключевое отличие от статичной модели).
    - Villain's bounty → 0.
    """
    n = len(stacks)
    if n < 2:
        raise ValueError("нужно >= 2 игрока")

    # Текущий $EV
    ev_current_list = bounty_icm_equity(
        stacks, bounties, prizes, n_simulations, seed
    )
    ev_current = ev_current_list[hero_idx]

    # Hero выигрывает (нокаутирует Villain)
    stacks_win = stacks.copy()
    stacks_win[hero_idx] += pot_bb
    stacks_win[villain_idx] -= pot_bb
    bounties_win = bounties.copy()
    # PKO: 50% bounty Villain → в bounty Hero (50% → кэш)
    bounties_win[hero_idx] += bounties[villain_idx] / 2
    bounties_win[villain_idx] = 0.0

    eq_win_list = bounty_icm_equity(
        stacks_win, bounties_win, prizes, n_simulations, seed
    )
    # + cash bounty за нокаут Villain
    ev_win = eq_win_list[hero_idx] + bounties[villain_idx] / 2

    # Hero проигрывает (сам нокаутирован)
    stacks_lose = stacks.copy()
    stacks_lose[hero_idx] -= pot_bb
    stacks_lose[villain_idx] += pot_bb
    bounties_lose = bounties.copy()
    bounties_lose[hero_idx] = 0.0
    bounties_lose[villain_idx] += bounties[hero_idx] / 2

    eq_lose_list = bounty_icm_equity(
        stacks_lose, bounties_lose, prizes, n_simulations, seed
    )
    ev_lose = eq_lose_list[hero_idx]

    d_win = ev_win - ev_current
    d_lose = ev_current - ev_lose

    if d_win <= 0:
        bf = float("inf")
    else:
        bf = d_lose / d_win

    icm_threshold = (
        d_lose / (d_win + d_lose) if (d_win + d_lose) > 0 else 0.5
    )

    return BountyBFResult(
        bf_hero=bf,
        icm_threshold=icm_threshold,
        ev_current=ev_current,
        ev_win=ev_win,
        ev_lose=ev_lose,
    )