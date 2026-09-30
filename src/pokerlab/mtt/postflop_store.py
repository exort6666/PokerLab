"""
Сохранение и загрузка постфлоп-стратегий (с u_root).

Имя файла: {street}_{board_hash}_pot{pot}_stk{stack}_{actor}.npz
Внутри .npz:
    node_keys  : np.array[str]
    str_<key>  : (169, n_actions) float32
    rank_table : (169,) int64
    u_root     : (169, 169) float32
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from pokerlab.config import PROJECT_ROOT
from pokerlab.mtt.postflop_cfr import PostflopStrategy
from pokerlab.mtt.postflop_tree import (
    PostflopAction, PostflopTreeConfig, Street,
)

STORE_DIR = Path(PROJECT_ROOT) / "data" / "postflop_strategies"
STORE_DIR.mkdir(parents=True, exist_ok=True)


def _board_hash(board: list[str]) -> str:
    return hashlib.sha1("|".join(sorted(board)).encode()).hexdigest()[:8]


def _filename(cfg: PostflopTreeConfig) -> str:
    return (f"{cfg.start_street.value}_{_board_hash(cfg.start_board)}_"
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
    cfg = res.cfg
    path = _path_for(cfg)
    node_keys = sorted(res.strategies.keys())
    arrays = {
        "node_keys": np.array(node_keys, dtype=object),
        "rank_table": res.rank_table,
    }
    if res.u_root is not None:
        arrays["u_root"] = res.u_root
    for key in node_keys:
        arrays[f"str_{_sanitize(key)}"] = res.strategies[key].astype(
            np.float32
        )
    np.savez_compressed(path, **arrays)

    meta = {
        "board": list(cfg.start_board),
        "board_hash": _board_hash(cfg.start_board),
        "street": cfg.start_street.value,
        "start_pot_bb": cfg.start_pot_bb,
        "start_stack_bb": cfg.start_stack_bb,
        "start_actor": cfg.start_actor,
        "bet_fractions": cfg.bet_fractions,
        "raise_multiplier": cfg.raise_multiplier,
        "iterations": res.iterations,
        "elapsed_sec": res.elapsed_sec,
        "node_keys": node_keys,
        "actions_of": {
            key: [_action_to_dict(a) for a in acts]
            for key, acts in res.actions_of.items()
        },
        "node_meta": res.node_meta,
    }
    path.with_suffix(".json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def load_postflop_strategy(
    cfg: PostflopTreeConfig,
) -> PostflopStrategy | None:
    path = _path_for(cfg)
    if not path.exists():
        return None
    meta_path = path.with_suffix(".json")
    if not meta_path.exists():
        return None

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    data = np.load(path, allow_pickle=True)
    node_keys = list(data["node_keys"])

    strategies = {
        key: data[f"str_{_sanitize(key)}"].astype(np.float64)
        for key in node_keys
    }
    actions_of = {
        key: [_action_from_dict(d) for d in lst]
        for key, lst in meta["actions_of"].items()
    }
    u_root = data["u_root"].astype(np.float32) if "u_root" in data else None

    return PostflopStrategy(
        strategies=strategies,
        actions_of=actions_of,
        node_meta=meta["node_meta"],
        board=list(meta["board"]),
        cfg=cfg,
        iterations=int(meta["iterations"]),
        elapsed_sec=float(meta["elapsed_sec"]),
        rank_table=data["rank_table"],
        u_root=u_root,
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
            print(f"  {f.name} | board={board_str} "
                  f"stack={meta.get('start_stack_bb')} "
                  f"iter={meta.get('iterations')}")


if __name__ == "__main__":
    cache_info()