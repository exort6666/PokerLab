"""
Bridge: средняя постфлоп-ценность для использования в префлопе.

Идея:
    На префлопе при узле goes_to_postflop мы не знаем борд заранее —
    он будет случайным из колоды. Значит используем усреднённый U_root
    по репрезентативной выборке бордов.

    U_avg[i,j] = среднее по K бордов U_root[i,j].

API:
    average_u_over_boards(cfgs, iterations, verbose) -> (169, 169)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import numpy as np

from pokerlab.mtt.cfr_pushfold import N_HANDS
from pokerlab.mtt.postflop_cfr import PostflopSolverVector
from pokerlab.mtt.postflop_store import (
    load_postflop_strategy, save_postflop_strategy,
)
from pokerlab.mtt.postflop_tree import PostflopTreeConfig, Street

log = logging.getLogger(__name__)


def get_u_root(
    cfg: PostflopTreeConfig,
    iterations: int = 5000,
    verbose: bool = False,
) -> np.ndarray:
    """Возвращает U_root (169,169) для борда. Берёт из кэша, если есть."""
    res = load_postflop_strategy(cfg)
    if res is not None and res.u_root is not None and \
            res.iterations >= iterations:
        if verbose:
            log.info("  cached: %s (iter=%d)",
                     "".join(cfg.start_board), res.iterations)
        return res.u_root
    if verbose:
        log.info("  solving: %s (%d iter)",
                 "".join(cfg.start_board), iterations)
    solver = PostflopSolverVector(cfg)
    res = solver.solve(iterations=iterations, log_every=0)
    save_postflop_strategy(res)
    return res.u_root


def average_u_over_boards(
    boards: list[list[str]],
    pot_bb: float = 6.0,
    stack_bb: float = 25.0,
    iterations: int = 5000,
    verbose: bool = True,
) -> np.ndarray:
    """
    Усредняет U_root по списку бордов.

    boards: список списков карт, например [["As","Ks","Qs"], ...].
    Возвращает (169,169) float32.
    """
    acc = np.zeros((N_HANDS, N_HANDS), dtype=np.float64)
    n = 0
    t0 = time.time()
    for i, board in enumerate(boards, 1):
        cfg = PostflopTreeConfig(
            start_pot_bb=pot_bb,
            start_stack_bb=stack_bb,
            start_board=board,
            start_street=Street.FLOP,
            start_actor="OOP",
        )
        u = get_u_root(cfg, iterations=iterations, verbose=verbose)
        acc += u
        n += 1
        if verbose:
            elapsed = time.time() - t0
            log.info("  [%d/%d] %s | %.1f сек",
                     i, len(boards), "".join(board), elapsed)
    avg = (acc / n).astype(np.float32)
    return avg


def save_average_u(
    avg: np.ndarray, name: str, meta: dict,
) -> Path:
    """Сохраняет усреднённый U в data/postflop_values/<name>.npz."""
    from pokerlab.config import PROJECT_ROOT
    d = Path(PROJECT_ROOT) / "data" / "postflop_values"
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{name}.npz"
    np.savez_compressed(path, u_avg=avg)
    import json
    (d / f"{name}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_average_u(name: str) -> np.ndarray | None:
    from pokerlab.config import PROJECT_ROOT
    path = Path(PROJECT_ROOT) / "data" / "postflop_values" / f"{name}.npz"
    if not path.exists():
        return None
    return np.load(path)["u_avg"].astype(np.float32)


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # 3 борда для теста
    boards = [
        ["As", "Ks", "Qs"],
        ["Kd", "7c", "2h"],
        ["8h", "7h", "6c"],
    ]
    print("Считаю U_root на 3 бордах (iter=500)...")
    avg = average_u_over_boards(
        boards, pot_bb=6.0, stack_bb=25.0, iterations=500, verbose=True,
    )
    print(f"\nU_avg shape = {avg.shape}")
    print(f"U_avg[AA, KK] = {avg[0, 1]:.3f}")
    print(f"U_avg[72o,32o] = {avg[-1, -2]:.3f}")

    name = "srp_25bb_pot6_test"
    save_average_u(avg, name, {
        "boards": ["".join(b) for b in boards],
        "pot_bb": 6.0, "stack_bb": 25.0, "iterations": 500,
    })
    print(f"Сохранено: data/postflop_values/{name}.npz")