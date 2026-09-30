"""
Сохранение и загрузка префлоп-стратегий (vector CFR и MC-DCFR).

Формат: .npz (сжатые numpy-массивы) + .json (метаданные).
Директория: data/preflop_strategies/

Имя файла кодирует ВСЕ параметры, влияющие на стратегию:
    {n}max_{stack}bb_{ante}ante_{model}.npz
    где model = "ae" (allin_equivalent) | "eo" (equity_only) | "na"

Это критично: при смене модели результат ДРУГОЙ, файлы не должны
перезаписывать друг друга.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Union

import numpy as np

from pokerlab.config import PROJECT_ROOT
from pokerlab.mtt.preflop_cfr import PreflopStrategy
from pokerlab.mtt.preflop_cfr_mc import PreflopStrategyMC
from pokerlab.mtt.preflop_tree import Action, ActionType, TreeConfig


AnyStrategy = Union[PreflopStrategy, PreflopStrategyMC]

STORE_DIR = Path(PROJECT_ROOT) / "data" / "preflop_strategies"
STORE_DIR.mkdir(parents=True, exist_ok=True)

# Короткие коды моделей
_MODEL_CODES = {
    "allin_equivalent": "ae",
    "equity_only": "eo",
    "": "na",
    None: "na",
}


def _model_code(model: str | None) -> str:
    return _MODEL_CODES.get(model, "na")


def _filename(cfg: TreeConfig, model: str | None = None) -> str:
    return (f"{cfg.n_players}max_"
            f"{cfg.stack_bb:06.2f}bb_"
            f"{cfg.ante_bb:04.2f}ante_"
            f"{_model_code(model)}.npz")


def _path_for(cfg: TreeConfig, model: str | None = None) -> Path:
    return STORE_DIR / _filename(cfg, model)


def _action_to_dict(a: Action) -> dict:
    return {"type": a.type.value, "amount_bb": a.amount_bb,
            "is_allin": a.is_allin, "short": a.short()}


def _action_from_dict(d: dict) -> Action:
    return Action(
        type=ActionType(d["type"]),
        amount_bb=float(d["amount_bb"]),
        is_allin=bool(d["is_allin"]),
    )


def _sanitize(key: str) -> str:
    return key.replace("/", "__").replace(":", "_")


def _serialize_meta(meta: dict) -> dict:
    out = {}
    for k, v in meta.items():
        if isinstance(v, dict):
            out[k] = {kk: float(vv) if isinstance(vv, (int, float))
                      else vv for kk, vv in v.items()}
        elif isinstance(v, list):
            out[k] = [list(t) if isinstance(t, tuple) else t for t in v]
        elif hasattr(v, "value"):
            out[k] = v.value
        else:
            out[k] = v
    return out


def save_strategy(res: AnyStrategy) -> Path:
    cfg = res.cfg
    model = getattr(res, "postflop_model", None)
    path = _path_for(cfg, model)

    node_keys = sorted(res.strategies.keys())
    arrays = {"node_keys": np.array(node_keys, dtype=object)}
    for key in node_keys:
        arrays[f"str_{_sanitize(key)}"] = res.strategies[key].astype(
            np.float32
        )
    np.savez_compressed(path, **arrays)

    actions_of_ser = {
        key: [_action_to_dict(a) for a in acts]
        for key, acts in res.actions_of.items()
    }
    node_meta_ser = {
        key: _serialize_meta(meta)
        for key, meta in res.node_meta.items()
    }
    meta = {
        "n_players": cfg.n_players,
        "stack_bb": cfg.stack_bb,
        "ante_bb": cfg.ante_bb,
        "open_size": cfg.open_size,
        "three_bet_size": cfg.three_bet_size,
        "four_bet_size": cfg.four_bet_size,
        "postflop_model": model,
        "iterations": res.iterations,
        "elapsed_sec": res.elapsed_sec,
        "node_keys": node_keys,
        "actions_of": actions_of_ser,
        "node_meta": node_meta_ser,
    }
    meta_path = path.with_suffix(".json")
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def load_strategy(cfg: TreeConfig,
                  model: str | None = "allin_equivalent"
                  ) -> PreflopStrategy | None:
    """
    Загружает стратегию. model — какой файл брать.
    None → ищем файл без суффикса модели (обратная совместимость).
    """
    path = _path_for(cfg, model)
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

    result = PreflopStrategy(
        strategies=strategies,
        actions_of=actions_of,
        node_meta=node_meta,
        cfg=cfg,
        iterations=int(meta["iterations"]),
        elapsed_sec=float(meta["elapsed_sec"]),
    )
    # Прикрепляем модель для последующего использования
    result.postflop_model = meta.get("postflop_model")
    return result


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
            print(f"  {f.name} | iter={meta.get('iterations')} "
                  f"| model={meta.get('postflop_model', '?')} "
                  f"| t={meta.get('elapsed_sec', 0):.1f}s")


if __name__ == "__main__":
    cache_info()