"""
Валидация CFR-ядра на чистом push/fold (без open/3bet).

Если CFR корректен — push range должен совпадать с Nash HU push/fold.

Трюк: заставляем open_size/3bet_size/4bet_size быть недостижимыми
(stack + 100). Тогда в дереве остаются только fold / allin —
чистое push/fold решение.

Эталон (Nash HU push/fold, SB push%, без анте):
   3 BB ~85%, 5 BB ~75%, 10 BB ~58%, 15 BB ~45%,
  20 BB ~40%, 25 BB ~35%, 30 BB ~30%.
"""

from __future__ import annotations

import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.preflop_cfr import PreflopSolver
from pokerlab.mtt.preflop_tree import TreeConfig, ActionType
from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS, COMBOS


def range_pct(hands: list[str]) -> float:
    total = sum(COMBOS[ALL_HANDS.index(h)] for h in hands)
    return total / 1326.0 * 100


def summarize(stack: float, iterations: int = 2000) -> None:
    # Делаем open/3bet/4bet невозможными → чистое push/fold.
    cfg = TreeConfig(
        n_players=2,
        stack_bb=stack,
        ante_bb=0.0,
        open_size=stack + 100,
        three_bet_size=stack + 100,
        four_bet_size=stack + 100,
    )
    solver = PreflopSolver(cfg)
    res = solver.solve(iterations=iterations, log_every=0)

    σ = res.strategies["ROOT"]
    actions = res.actions_of["ROOT"]

    idx_push = next(
        (i for i, a in enumerate(actions) if a.type == ActionType.ALLIN),
        None,
    )
    if idx_push is None:
        print(f"--- {stack:>5.1f} BB | НЕТ push-действия ---")
        return

    push_hands = [ALL_HANDS[i] for i in range(N_HANDS)
                  if σ[i, idx_push] > 0.5]

    print(f"--- {stack:>5.1f} BB | actions={[a.short() for a in actions]} ---")
    print(f"  push > 50%: {len(push_hands):>3} рук "
          f"({range_pct(push_hands):5.1f}%)")

    top_push = sorted(
        push_hands,
        key=lambda h: -σ[ALL_HANDS.index(h), idx_push],
    )
    print(f"  push top-15: {', '.join(top_push[:15])}")
    print()


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    print("Валидация CFR-ядра на ЧИСТОМ push/fold (без open/3bet).\n")
    for stack in (3, 5, 8, 10, 12, 15, 20, 25, 30):
        summarize(stack, iterations=2000)
    print("Эталон (Nash HU push/fold, SB push%):")
    print("   3 BB ~85%, 5 BB ~75%, 10 BB ~58%, 15 BB ~45%, "
          "20 BB ~40%, 25 BB ~35%, 30 BB ~30%.")


if __name__ == "__main__":
    main()