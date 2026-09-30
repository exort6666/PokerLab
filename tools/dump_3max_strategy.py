"""
Дамп 3-max стратегий на разных стеках.
Показывает BTN/SB/BB root-стратегии для AA, AKs, AQo, KQo, T9s, 72o.

Использование:
    python tools/dump_3max_strategy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.cfr_pushfold import ALL_HANDS
from pokerlab.mtt.preflop_store import (
    load_strategy, STORE_DIR,
)
from pokerlab.mtt.preflop_tree import TreeConfig


HANDS_TO_SHOW = ["AA", "KK", "QQ", "AKs", "AKo", "AQs",
                 "AJo", "KQo", "T9s", "72o"]


def show_stack(stack: float, model: str = "allin_equivalent") -> None:
    cfg = TreeConfig(n_players=3, stack_bb=stack, ante_bb=0.0)
    res = load_strategy(cfg, model=model)
    if res is None:
        print(f"  [нет файла для {stack} BB]")
        return

    print(f"=== {stack} BB ===")

    # ROOT = BTN
    for node_key in ["ROOT", "BTN__f", "BTN__r2.00", "BTN__aai"]:
        if node_key not in res.strategies:
            continue
        # Восстанавливаем нормальный ключ
        real_key = node_key.replace("__", "/").replace("_", ":")
        # Ищем совпадение
        real_key = None
        for k in res.strategies.keys():
            if k.replace("/", "__").replace(":", "_") == node_key:
                real_key = k
                break
        if real_key is None:
            continue

        sigma = res.strategies[real_key]
        actions = res.actions_of[real_key]
        actor = res.node_meta[real_key].get("actor", "?")

        header = " ".join(f"{a.short():>8}" for a in actions)
        print(f"  {real_key} (actor={actor}): {header}")
        for h in HANDS_TO_SHOW:
            i = ALL_HANDS.index(h)
            row = " ".join(f"{sigma[i, x]:8.3f}"
                           for x in range(len(actions)))
            print(f"    {h:>6} | {row}")
        print()


def main() -> None:
    print(f"Файлы в {STORE_DIR}:")
    for f in sorted(STORE_DIR.glob("3max_*.npz")):
        print(f"  {f.name}")
    print()

    for stack in (5, 10, 20, 30):
        show_stack(stack)


if __name__ == "__main__":
    main()