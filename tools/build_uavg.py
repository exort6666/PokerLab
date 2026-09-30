"""
Усредняет U_root по бордам для каждого config → U_avg.

Запуск:
    python tools/build_uavg.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.config import PROJECT_ROOT
from pokerlab.mtt.cfr_pushfold import N_HANDS
from pokerlab.mtt.postflop_store import (
    load_postflop_strategy, STORE_DIR,
)
from pokerlab.mtt.postflop_tree import PostflopTreeConfig, Street


# Должно совпадать с run_postflop_sweep.py
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
    "AsKsQs": ["As", "Ks", "Qs"],
    "8h7h6h": ["8h", "7h", "6h"],
    "KK2r":   ["Kd", "Kc", "2h"],
}

CONFIGS = [
    (4.5, 18.0, "srp_20bb"),
    (4.5, 28.0, "srp_30bb"),
    (4.5, 48.0, "srp_50bb"),
    (4.5, 68.0, "srp_75bb"),
    (4.5, 93.0, "srp_100bb"),
    (13.0, 24.0, "bp3_30bb"),
    (13.0, 47.0, "bp3_50bb"),
    (13.0, 62.0, "bp3_75bb"),
    (13.0, 87.0, "bp3_100bb"),
]s

OUT_DIR = Path(PROJECT_ROOT) / "data" / "postflop_values"


def build_one(cname: str, pot: float, stack: float) -> None:
    acc = np.zeros((N_HANDS, N_HANDS), dtype=np.float64)
    n = 0
    boards_used = []
    for label, board in BOARDS.items():
        cfg = PostflopTreeConfig(
            start_pot_bb=pot, start_stack_bb=stack,
            start_board=board, start_street=Street.FLOP,
            start_actor="OOP",
        )
        res = load_postflop_strategy(cfg)
        if res is None or res.u_root is None:
            print(f"  [miss] {label} / {cname}")
            continue
        acc += res.u_root
        n += 1
        boards_used.append(label)

    if n == 0:
        print(f"  {cname}: 0 бордов, пропускаем")
        return

    avg = (acc / n).astype(np.float32)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{cname}.npz"
    np.savez_compressed(path, u_avg=avg)
    meta = {
        "config_name": cname,
        "pot_bb": pot,
        "stack_bb": stack,
        "n_boards": n,
        "boards": boards_used,
    }
    (OUT_DIR / f"{cname}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"  {cname}: {n} бордов → {path.name}")


def main() -> None:
    print(f"Строю U_avg из {STORE_DIR}")
    for pot, stack, cname in CONFIGS:
        build_one(cname, pot, stack)


if __name__ == "__main__":
    main()