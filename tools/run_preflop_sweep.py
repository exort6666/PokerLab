"""
Пакетный расчёт префлоп-стратегий по сетке стеков / анте / форматов.

Два движка:
    --engine vector  — Vector CFR (только 2-max, максимальная точность).
    --engine mc      — Monte-Carlo DCFR (любой N-max).
    --engine auto    — 2-max → vector, 3+ → mc.

Модель постфлопа:
    --postflop-model allin_equivalent  (по умолчанию, рабочая)
    --postflop-model equity_only       (вырождается, не использовать)

Примеры:
    python tools/run_preflop_sweep.py --quick
    python tools/run_preflop_sweep.py --n 3 --stacks 5 10 20 --iterations 200000
    python tools/run_preflop_sweep.py --engine vector
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

from pokerlab.mtt.preflop_cfr import PreflopSolver
from pokerlab.mtt.preflop_cfr_mc import PreflopSolverMC
from pokerlab.mtt.preflop_store import save_strategy, load_strategy
from pokerlab.mtt.preflop_tree import TreeConfig


log = logging.getLogger(__name__)


def _choose_engine(engine: str, n_players: int) -> str:
    if engine == "auto":
        return "vector" if n_players == 2 else "mc"
    return engine


def run_one(job: dict) -> dict:
    cfg = TreeConfig(
        n_players=job["n_players"],
        stack_bb=job["stack_bb"],
        ante_bb=job["ante_bb"],
    )
    engine = job["engine"]
    model = job["postflop_model"]
    t0 = time.time()
    model_tag = model.split("_")[0][:2] if model else "na"
    key = (f"{job['n_players']}max_{job['stack_bb']:.0f}bb_"
           f"{job['ante_bb']:.2f}ante[{engine},{model_tag}]")

    try:
        if job.get("skip_existing", True):
            existing = load_strategy(cfg, model=model)
            if (existing is not None
                    and existing.iterations >= job["iterations"]):
                return {"ok": True, "skipped": True, "key": key,
                        "elapsed": 0.0}

        if engine == "vector":
            if cfg.n_players != 2:
                return {"ok": False, "key": key,
                        "error": "vector CFR — только 2-max",
                        "elapsed": 0.0}
            solver = PreflopSolver(cfg)
        else:
            solver = PreflopSolverMC(cfg, postflop_model=model)

        res = solver.solve(iterations=job["iterations"], log_every=0)
        save_strategy(res)
        return {"ok": True, "skipped": False, "key": key,
                "elapsed": time.time() - t0}
    except Exception as e:
        return {"ok": False, "key": key, "error": str(e),
                "elapsed": time.time() - t0}


def build_grid(n_players_list, stacks, antes, iterations,
               skip_existing, engine, postflop_model):
    jobs = []
    for n in n_players_list:
        eng = _choose_engine(engine, n)
        for stack in stacks:
            for ante in antes:
                jobs.append({
                    "n_players": n,
                    "stack_bb": stack,
                    "ante_bb": ante,
                    "iterations": iterations,
                    "skip_existing": skip_existing,
                    "engine": eng,
                    "postflop_model": postflop_model,
                })
    return jobs


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--n", type=int, nargs="+", default=[2, 3])
    p.add_argument("--stacks", type=float, nargs="+",
                   default=[5, 8, 10, 12, 15, 20, 25, 30])
    p.add_argument("--antes", type=float, nargs="+", default=[0.0])
    p.add_argument("--iterations", type=int, default=5000)
    p.add_argument("--engine", choices=["vector", "mc", "auto"],
                   default="auto")
    p.add_argument("--postflop-model",
                   choices=["allin_equivalent", "equity_only"],
                   default="allin_equivalent")
    p.add_argument("--quick", action="store_true")
    p.add_argument("--workers", type=int, default=0)
    p.add_argument("--no-skip", action="store_true")
    args = p.parse_args()

    logging.basicConfig(level=logging.WARNING)

    if args.quick:
        args.n = [2]
        args.stacks = [10, 20, 30]
        args.iterations = 500

    jobs = build_grid(
        args.n, args.stacks, args.antes, args.iterations,
        not args.no_skip, args.engine, args.postflop_model,
    )

    n_workers = args.workers or max(1, (os.cpu_count() or 1) - 1)
    print(f"Всего задач: {len(jobs)}")
    print(f"Ядер: {os.cpu_count()}, воркеров: {n_workers}")
    print(f"Итераций: {args.iterations}")
    print(f"Engine: {args.engine}")
    print(f"Postflop model: {args.postflop_model}")
    print()

    t0 = time.time()
    with mp.Pool(processes=n_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(run_one, jobs), 1):
            elapsed_total = time.time() - t0
            status = "OK " if result["ok"] else "ERR"
            skip = " [skip]" if result.get("skipped") else ""
            if result["ok"]:
                print(f"[{i:>3}/{len(jobs)}] {status} "
                      f"{result['key']:<40} "
                      f"({result['elapsed']:6.1f}s){skip} "
                      f"| total {elapsed_total:6.0f}s")
            else:
                print(f"[{i:>3}/{len(jobs)}] {status} "
                      f"{result['key']:<40} "
                      f"({result['elapsed']:6.1f}s) "
                      f"| ERROR: {result['error']}")

    total = time.time() - t0
    print()
    print(f"ГОТОВО за {total:.0f}s ({total/60:.1f} мин)")


if __name__ == "__main__":
    main()