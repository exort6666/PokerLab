"""
Проверка сходимости постфлоп-CFR (параллельная версия).

4 прогона параллельно: 500 / 1000 / 1500 / 2000 итераций.
Время: ~7-8 минут (max = 2000 итераций).
"""

from __future__ import annotations

import multiprocessing as mp
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS
from pokerlab.mtt.postflop_cfr import PostflopSolverVector
from pokerlab.mtt.postflop_tree import PostflopTreeConfig, Street


def _make_cfg() -> PostflopTreeConfig:
    return PostflopTreeConfig(
        start_pot_bb=6.0,
        start_stack_bb=25.0,
        start_board=["As", "Ks", "Qs"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )


def _run_one_worker(iters: int):
    """Worker: N итераций. Возвращает (iters, elapsed, sigma_root, actions)."""
    t0 = time.time()
    cfg = _make_cfg()
    solver = PostflopSolverVector(cfg)
    res = solver.solve(iterations=iters, log_every=0)
    elapsed = time.time() - t0

    sigma = None
    actions = None
    for k in res.strategies:
        if not res.node_meta[k].get("history"):
            sigma = res.strategies[k]
            actions = res.actions_of[k]
            break
    return iters, elapsed, sigma, actions


def print_summary(results: dict, actions: list) -> None:
    print()
    print("=" * 78)
    print("Сравнение стратегий ROOT")
    print("=" * 78)
    print(f"Actions: {[a.value for a in actions]}")
    print()

    keys = sorted(results.keys())

    print("Max |σ_a − σ_b| между прогонами (чем меньше — тем стабильнее):")
    print(f"{'':>8} | " + " ".join(f"{k:>8}" for k in keys))
    print("-" * (11 + 9 * len(keys)))
    for k1 in keys:
        row = [f"{k1:>8}"]
        for k2 in keys:
            if k2 < k1:
                row.append(f"{'--':>8}")
            else:
                diff = float(np.abs(results[k1] - results[k2]).max())
                row.append(f"{diff:>8.4f}")
        print(" | ".join(row))

    print()
    print("Ключевые руки на ROOT (сравнение стратегий):")
    n_actions = results[keys[0]].shape[1]
    for h in ("AA", "AKo", "AQs", "72o"):
        i = ALL_HANDS.index(h)
        print(f"\n  {h}:")
        for k in keys:
            row = " ".join(f"{results[k][i, a]:6.3f}"
                           for a in range(n_actions))
            print(f"    iter={k:>5}: {row}")

    print()
    print(f"=== Полная ROOT-стратегия для {keys[-1]} итераций ===")
    print(f"{'Hand':>6} | " + " ".join(f"{a.value:>6}" for a in actions))
    sigma = results[keys[-1]]
    for h in ("AA", "KK", "QQ", "AKs", "AKo", "AQs", "AQo",
              "AJs", "A9s", "T9s", "72o", "32o"):
        i = ALL_HANDS.index(h)
        row = " ".join(f"{sigma[i, a]:6.3f}"
                       for a in range(n_actions))
        print(f"{h:>6} | {row}")

    # --- Итоговый вердикт ---
    print()
    print("=" * 78)
    print("ВЕРДИКТ:")
    print("=" * 78)
    if len(keys) >= 2:
        diff_last = float(np.abs(results[keys[-1]] - results[keys[-2]]).max())
        if diff_last < 0.05:
            print(f"  diff между {keys[-2]} и {keys[-1]} = {diff_last:.4f}")
            print(f"  → стабилизировалось. Можно использовать {keys[-2]} итераций.")
        elif diff_last < 0.10:
            print(f"  diff между {keys[-2]} и {keys[-1]} = {diff_last:.4f}")
            print(f"  → почти стабильно. Нужно {keys[-1]}+ итераций.")
        else:
            print(f"  diff между {keys[-2]} и {keys[-1]} = {diff_last:.4f}")
            print(f"  → НЕ стабилизировалось. Нужно больше итераций.")


def main() -> None:
    print("Проверка сходимости постфлоп-CFR (parallel)")
    print("Борд: AsKsQs, HU SRP, pot=6, stack=25, OOP first")
    print("Итерации: 500 / 1000 / 1500 / 2000 (4 процесса)")
    print()

    iters_list = [500, 1000, 1500, 2000]

    t0 = time.time()
    results: dict = {}
    actions = None

    # map с сохранением порядка
    with mp.Pool(processes=4) as pool:
        for iters, elapsed, sigma, acts in pool.map(
            _run_one_worker, iters_list
        ):
            print(f"  {iters:>5} iter готово за {elapsed:6.1f} сек",
                  flush=True)
            results[iters] = sigma
            if actions is None:
                actions = acts

    total = time.time() - t0
    print()
    print(f"Общее время (parallel): {total:.1f} сек "
          f"({total/60:.1f} мин)")

    print_summary(results, actions)


if __name__ == "__main__":
    main()