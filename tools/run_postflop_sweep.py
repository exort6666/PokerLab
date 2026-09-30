"""
Пакетный расчёт постфлоп-стратегий по сетке бордов (HU SRP).

Запуск:
    python tools/run_postflop_sweep.py --quick
    python tools/run_postflop_sweep.py --boards flop_dry flop_monotone ...
    python tools/run_postflop_sweep.py --stacks 20 50 100
"""

from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.postflop_cfr import PostflopSolverVector
from pokerlab.mtt.postflop_store import (
    save_postflop_strategy, load_postflop_strategy,
)
from pokerlab.mtt.postflop_tree import (
    PostflopTreeConfig, Street, build_postflop_tree, count_nodes,
)


# Согласованные борды для sweep.
# Каждый — репрезентант своего класса (dry/monotone/paired/broadway).
BOARDS = {
    # Dry
    "K72r":    (["Kd", "7c", "2h"], "flop"),
    "A83r":    (["Ad", "8c", "3h"], "flop"),
    # Monotone
    "AsKsQs":  (["As", "Ks", "Qs"], "flop"),
    "8h7h6h":  (["8h", "7h", "6h"], "flop"),
    # Paired
    "KK2r":    (["Kd", "Kc", "2h"], "flop"),
    "TT4r":    (["Td", "Tc", "4h"], "flop"),
    # Broadway
    "QJT":     (["Qh", "Jd", "Tc"], "flop"),
    "AJTss":   (["Ah", "Jh", "Th"], "flop"),
    # Low
    "654r":    (["6d", "5c", "4h"], "flop"),
    "422r":    (["4d", "2c", "2h"], "flop"),
}


def run_one(job: dict) -> dict:
    board = job["board"]
    street = Street(job["street"])
    cfg = PostflopTreeConfig(
        start_pot_bb=job["pot_bb"],
        start_stack_bb=job["stack_bb"],
        start_board=board,
        start_street=street,
        start_actor="OOP",
    )
    key = f"{job['label']}_{job['stack_bb']:.0f}bb"

    t0 = time.time()
    try:
        if job.get("skip_existing", True):
            existing = load_postflop_strategy(cfg)
            if (existing is not None
                    and existing.iterations >= job["iterations"]):
                return {"ok": True, "skipped": True, "key": key,
                        "elapsed": 0.0}

        solver = PostflopSolverVector(cfg)
        res = solver.solve(iterations=job["iterations"], log_every=0)
        save_postflop_strategy(res)
        return {"ok": True, "skipped": False, "key": key,
                "elapsed": time.time() - t0}
    except Exception as e:
        return {"ok": False, "key": key, "error": str(e),
                "elapsed": time.time() - t0}


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--boards", type=str, nargs="+",
                   default=None,
                   help=f"Ключи из {list(BOARDS.keys())}")
    p.add_argument("--stacks", type=float, nargs="+",
                   default=[25.0])
    p.add_argument("--pots", type=float, nargs="+",
                   default=[6.0],
                   help="Размер пота на флопе (для SRP ~6)")
    p.add_argument("--iterations", type=int, default=2000)
    p.add_argument("--quick", action="store_true",
                   help="2 борда, 1 стек, 500 итераций")
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--no-skip", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if args.quick:
        args.boards = ["AsKsQs", "K72r"]
        args.stacks = [25.0]
        args.iterations = 500

    board_keys = args.boards or list(BOARDS.keys())

    jobs = []
    for label in board_keys:
        if label not in BOARDS:
            print(f"Неизвестный борд: {label}")
            continue
        board, street = BOARDS[label]
        for stack in args.stacks:
            for pot in args.pots:
                jobs.append({
                    "label": label,
                    "board": board,
                    "street": street,
                    "pot_bb": pot,
                    "stack_bb": stack,
                    "iterations": args.iterations,
                    "skip_existing": not args.no_skip,
                })

    n_workers = args.workers or max(1, (os.cpu_count() or 1) - 1)
    print(f"Всего задач: {len(jobs)}")
    print(f"Ядер: {os.cpu_count()}, воркеров: {n_workers}")
    print(f"Итераций: {args.iterations}")
    print()

    t0 = time.time()
    with mp.Pool(processes=n_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(run_one, jobs), 1):
            elapsed_total = time.time() - t0
            status = "OK " if result["ok"] else "ERR"
            skip = " [skip]" if result.get("skipped") else ""
            if result["ok"]:
                print(f"[{i:>3}/{len(jobs)}] {status} "
                      f"{result['key']:<20} "
                      f"({result['elapsed']:7.1f}s){skip} "
                      f"| total {elapsed_total:6.0f}s")
            else:
                print(f"[{i:>3}/{len(jobs)}] {status} "
                      f"{result['key']:<20} "
                      f"({result['elapsed']:7.1f}s) "
                      f"| ERROR: {result['error']}")

    total = time.time() - t0
    print()
    print(f"ГОТОВО за {total:.0f}s ({total/60:.1f} мин)")


if __name__ == "__main__":
    main()