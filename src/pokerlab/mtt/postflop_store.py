"""
Сохранение и загрузка постфлоп-стратегий (vector CFR).

Формат: .npz (сжатые numpy-массивы) + .json (метаданные).
Директория: data/postflop_strategies/

Имя файла кодирует параметры:
    {street}_{board_hash}_{pot}bb_{stack}bb_{ip|oop}.npz

board_hash = первые 8 hex-символов sha1 от отсортированного борда.
Отсортировано — чтобы [As,Ks,Qs] и [Ks,As,Qs] давали один hash.

Внутри .npz:
    node_keys  : np.array[str]
    str_<key>  : np.ndarray (169, n_actions) float32
    rank_table : np.ndarray (169,) int64 — сила каждой руки с бордом

Метаданные .json:
    {
      "board": [...],
      "street": "flop",
      "start_pot_bb": float,
      "start_stack_bb": float,
      "start_actor": "OOP"|"IP",
      "iterations": int,
      "elapsed_sec": float,
      "actions_of": { node_key: [action_dict, ...] },
      "node_meta": { node_key: {...} }
    }
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Union

import numpy as np

from pokerlab.config import PROJECT_ROOT
from pokerlab.mtt.postflop_cfr import PostflopStrategy
from pokerlab.mtt.postflop_tree import (
    PostflopAction, PostflopTreeConfig, Street,
)


STORE_DIR = Path(PROJECT_ROOT) / "data" / "postflop_strategies"
STORE_DIR.mkdir(parents=True, exist_ok=True)


def _board_hash(board: list[str]) -> str:
    """Стабильный hash борда (не зависит от порядка карт)."""
    key = "|".join(sorted(board))
    return hashlib.sha1(key.encode()).hexdigest()[:8]


def _filename(cfg: PostflopTreeConfig) -> str:
    bh = _board_hash(cfg.start_board)
    return (f"{cfg.start_street.value}_{bh}_"
            f"pot{cfg.start_pot_bb:.1f}_"
            f"stk{cfg.start_stack_bb:.1f}_"
            f"{cfg.start_actor.lower()}.npz")


def _path_for(cfg: PostflopTreeConfig) -> Path:
    return STORE_DIR / _filename(cfg)


def _sanitize(key: str) -> str:
    return key.replace("/", "__").replace(":", "_").replace("|", "_")


def _action_to_dict(a: PostflopAction) -> dict:
    return {"value": a.value}


def _action_from_dict(d: dict) -> PostflopAction:
    return PostflopAction(d["value"])


def save_postflop_strategy(res: PostflopStrategy) -> Path:
    """Сохраняет постфлоп-стратегию в .npz + .json."""
    cfg = res.cfg
    path = _path_for(cfg)

    node_keys = sorted(res.strategies.keys())
    arrays = {
        "node_keys": np.array(node_keys, dtype=object),
        "rank_table": res.rank_table,
    }
    for key in node_keys:
        arrays[f"str_{_sanitize(key)}"] = res.strategies[key].astype(
            np.float32
        )
    np.savez_compressed(path, **arrays)

    actions_of_ser = {
        key: [_action_to_dict(a) for a in acts]
        for key, acts in res.actions_of.items()
    }
    meta = {
        "board": list(cfg.start_board),
        "board_hash": _board_hash(cfg.start_board),
        "street": cfg.start_street.value,
        "start_pot_bb": cfg.start_pot_bb,
        "start_stack_bb": cfg.start_stack_bb,
        "start_actor": cfg.start_actor,
        "bet_fractions": cfg.bet_fractions,
        "raise_multiplier": cfg.raise_multiplier,
        "max_raises_per_street": cfg.max_raises_per_street,
        "iterations": res.iterations,
        "elapsed_sec": res.elapsed_sec,
        "node_keys": node_keys,
        "actions_of": actions_of_ser,
        "node_meta": res.node_meta,
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def load_postflop_strategy(
    cfg: PostflopTreeConfig,
) -> PostflopStrategy | None:
    """Загружает постфлоп-стратегию. None, если файла нет."""
    path = _path_for(cfg)
    if not path.exists():
        return None
    meta_path = path.with_suffix(".json")
    if not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    data = np.load(path, allow_pickle=True)
    node_keys = list(data["node_keys"])

    strategies: dict[str, np.ndarray] = {}
    for key in node_keys:
        arr = data[f"str_{_sanitize(key)}"]
        strategies[key] = arr.astype(np.float64)

    actions_of: dict[str, list] = {
        key: [_action_from_dict(d) for d in lst]
        for key, lst in meta["actions_of"].items()
    }
    node_meta: dict[str, dict] = meta["node_meta"]
    rank_table = data["rank_table"]

    return PostflopStrategy(
        strategies=strategies,
        actions_of=actions_of,
        node_meta=node_meta,
        board=list(meta["board"]),
        cfg=cfg,
        iterations=int(meta["iterations"]),
        elapsed_sec=float(meta["elapsed_sec"]),
        rank_table=rank_table,
    )


def list_available() -> list[Path]:
    return sorted(STORE_DIR.glob("*.npz"))


def cache_info() -> None:
    files = list_available()
    print(f"Хранилище: {STORE_DIR}")
    print(f"Файлов: {len(files)}")
    for f in files:
        meta_path = f.with_suffix(".json")
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            board_str = "".join(meta.get("board", []))
            print(f"  {f.name}")
            print(f"    board={board_str} street={meta.get('street')} "
                  f"pot={meta.get('start_pot_bb')} "
                  f"stack={meta.get('start_stack_bb')} "
                  f"iter={meta.get('iterations')} "
                  f"t={meta.get('elapsed_sec', 0):.1f}s")


if __name__ == "__main__":
    cache_info()