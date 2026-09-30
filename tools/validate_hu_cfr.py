"""
Сравнение CFR-результата с известными HU push/fold чартами.

Прогоняет 2-max на коротких стеках (3..30 BB) и печатает:
    - долю рук, идущих в push (allin) с частотой > 50%
    - долю рук, идущих в open 2x с частотой > 50%
    - v_sb (средняя полезность SB)

Если на 10 BB push ≈ 55–60%, а на 20 BB ≈ 40–45% — код работает.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.preflop_cfr import PreflopSolver
from pokerlab.mtt.preflop_tree import TreeConfig
from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS, COMBOS


def range_pct(hands: list[str]) -> float:
    total = sum(COMBOS[ALL_HANDS.index(h)] for h in hands)
    return total / 1326.0 * 100


def summarize(stack: float, iterations: int = 500) -> None:
    cfg = TreeConfig(n_players=2, stack_bb=stack, ante_bb=0.0)
    solver = PreflopSolver(cfg)
    res = solver.solve(iterations=iterations, log_every=0)

    σ = res.strategies["ROOT"]
    actions = res.actions_of["ROOT"]

    # Колонки: f=0, aai=1, r2=2
    fold_hands = [ALL_HANDS[i] for i in range(N_HANDS)
                  if σ[i, 0] > 0.5]
    push_hands = [ALL_HANDS[i] for i in range(N_HANDS)
                  if σ[i, 1] > 0.5]
    open_hands = [ALL_HANDS[i] for i in range(N_HANDS)
                  if σ[i, 2] > 0.5]

    # Доминирующее действие
    dom_push = [ALL_HANDS[i] for i in range(N_HANDS)
                if σ[i, 1] == σ[i].max()]
    dom_fold = [ALL_HANDS[i] for i in range(N_HANDS)
                if σ[i, 0] == σ[i].max()]

    print(f"--- {stack:>5.1f} BB ---")
    print(f"  push  > 50%: {len(push_hands):>3} рук "
          f"({range_pct(push_hands):5.1f}%)")
    print(f"  open  > 50%: {len(open_hands):>3} рук "
          f"({range_pct(open_hands):5.1f}%)")
    print(f"  fold  > 50%: {len(fold_hands):>3} рук")
    print(f"  dominant push: {range_pct(dom_push):5.1f}% | "
          f"dominant fold: {range_pct(dom_fold):5.1f}%")

    top_push = sorted(push_hands, key=lambda h: -σ[ALL_HANDS.index(h), 1])
    print(f"  push top-15: {', '.join(top_push[:15])}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    print("Проверка: 2-max HU, разные стеки.\n")
    for stack in (3, 5, 8, 10, 12, 15, 20, 25, 30):
        summarize(stack, iterations=500)
    print("Ожидание (Nash HU push/fold):")
    print("   3 BB  → push ~85%")
    print("   5 BB  → push ~75%")
    print("  10 BB  → push ~58%")
    print("  15 BB  → push ~45%")
    print("  20 BB  → push ~40%")
    print("  30 BB  → push ~30% (и часть идёт в open, не push)")


if __name__ == "__main__":
    main()