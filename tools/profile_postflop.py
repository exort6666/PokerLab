"""
Профилирование постфлоп-CFR: где тратится время.

Запуск:
    python tools/profile_postflop.py
    python tools/profile_postflop.py --iters 30    # для быстрого анализа
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.postflop_cfr import PostflopSolverVector
from pokerlab.mtt.postflop_tree import (
    PostflopTreeConfig, Street, build_postflop_tree, count_nodes,
)


def build_solver() -> PostflopSolverVector:
    cfg = PostflopTreeConfig(
        start_pot_bb=6.0,
        start_stack_bb=25.0,
        start_board=["As", "Ks", "Qs"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )
    return PostflopSolverVector(cfg)


def run_profile(iters: int) -> None:
    print(f"=== Профилирование {iters} итераций ===")
    solver = build_solver()
    print(f"Узлов: {len(solver.regret)}")
    print()

    # Прогрев — заполнить кэши
    print("Прогрев (5 итераций)...")
    solver.solve(iterations=5, log_every=0)
    print()

    # Профилирование
    solver2 = build_solver()
    pr = cProfile.Profile()
    pr.enable()
    solver2.solve(iterations=iters, log_every=0)
    pr.disable()

    # Вывод топ-25 функций по cumulative time
    s = io.StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
    ps.print_stats(25)
    print(s.getvalue())

    # Также по total time
    s2 = io.StringIO()
    ps2 = pstats.Stats(pr, stream=s2).sort_stats("tottime")
    ps2.print_stats(15)
    print("=== Топ по tottime ===")
    print(s2.getvalue())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--iters", type=int, default=30)
    args = p.parse_args()

    run_profile(args.iters)


if __name__ == "__main__":
    main()