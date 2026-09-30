"""
Валидация MC-CFR на 3-max push/fold.

Отключаем open/3bet/4bet (делаем недостижимыми), оставляем только
fold/allin. Сравниваем с ожидаемыми 3-max push/fold чартами:
    BTN push на 10 BB ≈ 45–55% рук
    BTN push на 20 BB ≈ 25–35% рук
    BTN push на 30 BB ≈ 15–25% рук
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.preflop_cfr_mc import PreflopSolverMC, range_pct
from pokerlab.mtt.preflop_tree import TreeConfig, ActionType
from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS


def summarize(stack: float, iterations: int = 200_000) -> None:
    cfg = TreeConfig(
        n_players=3,
        stack_bb=stack,
        ante_bb=0.0,
        open_size=stack + 100,
        three_bet_size=stack + 100,
        four_bet_size=stack + 100,
    )
    solver = PreflopSolverMC(cfg, seed=42)
    res = solver.solve(iterations=iterations, log_every=0)

    sigma = res.strategies["ROOT"]
    actions = res.actions_of["ROOT"]
    actor = res.node_meta["ROOT"]["actor"]
    idx_push = next(i for i, a in enumerate(actions)
                    if a.type == ActionType.ALLIN)

    push = [ALL_HANDS[i] for i in range(N_HANDS)
            if sigma[i, idx_push] > 0.5]
    print(f"--- {stack:>5.1f} BB | actor={actor} | "
          f"actions={[a.short() for a in actions]} ---")
    print(f"  push > 50%: {len(push):>3} рук "
          f"({range_pct(push):5.1f}%)")
    top = sorted(push, key=lambda h: -sigma[ALL_HANDS.index(h), idx_push])[:15]
    print(f"  top-15: {', '.join(top)}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    print("Валидация MC-CFR на 3-max push/fold.\n")
    for stack in (5, 10, 15, 20, 30):
        summarize(stack, iterations=200_000)
    print("Эталон (BTN open-push, 3-max):")
    print("   5 BB ~70%, 10 BB ~50%, 15 BB ~35%, 20 BB ~28%, 30 BB ~18%")


if __name__ == "__main__":
    main()