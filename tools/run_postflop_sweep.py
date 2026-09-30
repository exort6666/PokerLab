"""
Пакетный расчёт постфлоп-стратегий для grid (board × config).

Config = (pot, stack, name) — конкретные пары, которые реально
встречаются в префлоп-дереве. НЕ cross-product pots × stacks.

Запуск:
    python tools/run_postflop_sweep.py --quick
    python tools/run_postflop_sweep.py --iterations 5000 --workers 3
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
    PostflopTreeConfig, Street,
)


# 15 репрезентативных бордов
BOARDS = {
    "A72r":   ["Ad", "7c", "2h"],
    "A83r":   ["Ad", "8c", "3h"],
    "AK4r":   ["Ad", "Kc", "4h"],
    "A95ss":  ["Ah", "9h", "5c"],
    "K72r":   ["Kd", "7c", "2h"],
    "KQ4r":   ["Kd", "Qc", "4h"],
    "K95ss":  ["Kh", "9h", "5c"],
    "Q72r":   ["Qd", "7c", "2h"],
    "QJ4r":   ["Qd", "Jc", "4h"],
    "JT9r":   ["Jd", "Tc", "9h"],
    "T98r":   ["Td", "9c", "8h"],
    "987r":   ["9d", "8c", "7h"],
    "AsKsQs": ["As", "Ks", "Qs"],  # monotone
    "8h7h6h": ["8h", "7h", "6h"],  # monotone low
    "KK2r":   ["Kd", "Kc", "2h"],  # paired
}

# Configs: (pot, stack, name)
# Configs: (pot, stack, name)
CONFIGS = [
    # SRP
    (4.5, 18.0, "srp_20bb"),
    (4.5, 28.0, "srp_30bb"),
    (4.5, 48.0, "srp_50bb"),
    (4.5, 68.0, "srp_75bb"),
    (4.5, 93.0, "srp_100bb"),
    # 3BP
    (13.0, 24.0, "bp3_30bb"),
    (13.0, 47.0, "bp3_50bb"),
    (13.0, 62.0, "bp3_75bb"),
    (13.0, 87.0, "bp3_100bb"),
]

def run_one(job: dict) -> dict:
    cfg = PostflopTreeConfig(
        start_pot_bb=job["pot"],
        start_stack_bb=job["stack"],
        start_board=job["board"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )
    key = f"{job['label']}_{job['config_name']}"

    t0 = time.time()
    try:
        if job.get("skip_existing", True):
            ex = load_postflop_strategy(cfg)
            if ex is not None and ex.u_root is not None and \
                    ex.iterations >= job["iterations"]:
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
    p.add_argument("--iterations", type=int, default=5000)
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=3)
    p.add_argument("--no-skip", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)

    boards = BOARDS
    configs = CONFIGS
    iterations = args.iterations
    if args.quick:
        boards = {"AsKsQs": ["As", "Ks", "Qs"]}
        configs = [(4.5, 18.0, "srp_20bb")]
        iterations = 300

    jobs = []
    for label, board in boards.items():
        for pot, stack, cname in configs:
            jobs.append({
                "label": label, "board": board,
                "pot": pot, "stack": stack,
                "config_name": cname,
                "iterations": iterations,
                "skip_existing": not args.no_skip,
            })

    print(f"Всего задач: {len(jobs)}")
    print(f"Бордов: {len(boards)}, конфигов: {len(configs)}")
    print(f"Итераций: {iterations}")
    print(f"Воркеров: {args.workers}")
    print()

    t0 = time.time()
    with mp.Pool(processes=args.workers) as pool:
        for i, r in enumerate(pool.imap_unordered(run_one, jobs), 1):
            et = time.time() - t0
            st = "OK " if r["ok"] else "ERR"
            sk = " [skip]" if r.get("skipped") else ""
            if r["ok"]:
                print(f"[{i:>3}/{len(jobs)}] {st} {r['key']:<20} "
                      f"({r['elapsed']:7.1f}s){sk} | total {et:6.0f}s",
                      flush=True)
            else:
                print(f"[{i:>3}/{len(jobs)}] {st} {r['key']:<20} "
                      f"({r['elapsed']:7.1f}s) ERR: {r['error']}",
                      flush=True)

    print()
    print(f"ГОТОВО за {(time.time()-t0)/60:.1f} мин")


if __name__ == "__main__":
    main()