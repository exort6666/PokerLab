"""
Просмотр сохранённой постфлоп-стратегии.

Использование:
    python tools/dump_postflop_strategy.py
    python tools/dump_postflop_strategy.py --board AsKsQs --street flop
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.mtt.cfr_pushfold import ALL_HANDS
from pokerlab.mtt.postflop_store import (
    load_postflop_strategy, list_available, STORE_DIR,
)
from pokerlab.mtt.postflop_tree import PostflopTreeConfig, Street


HANDS_TO_SHOW = [
    "AA", "KK", "QQ", "AKs", "AKo", "AQs", "AQo",
    "AJs", "KQs", "A9s", "T9s", "98s", "76s", "72o",
]


def show(res, top_n: int = len(HANDS_TO_SHOW)) -> None:
    # Найдём root
    root_key = None
    for k in res.strategies:
        if not res.node_meta[k].get("history"):
            root_key = k
            break
    if root_key is None:
        print("ROOT не найден")
        return

    sigma = res.strategies[root_key]
    actions = res.actions_of[root_key]
    actor = res.node_meta[root_key]["actor"]

    print(f"Борд: {''.join(res.board)} | "
          f"street={res.node_meta[root_key]['street']} | "
          f"pot={res.cfg.start_pot_bb} BB | "
          f"stack={res.cfg.start_stack_bb} BB")
    print(f"ROOT actor={actor}, "
          f"actions={[a.value for a in actions]}")
    print()
    print(f"{'Hand':>6} | " + " ".join(f"{a.value:>6}"
                                        for a in actions))
    print("-" * 60)
    for h in HANDS_TO_SHOW[:top_n]:
        i = ALL_HANDS.index(h)
        row = " ".join(f"{sigma[i, a]:6.3f}"
                       for a in range(len(actions)))
        print(f"{h:>6} | {row}")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--board", type=str, default=None,
                   help="Например AsKsQs")
    p.add_argument("--street", type=str, default="flop")
    p.add_argument("--pot", type=float, default=6.0)
    p.add_argument("--stack", type=float, default=25.0)
    p.add_argument("--list", action="store_true",
                   help="Только список сохранённых файлов")
    args = p.parse_args()

    if args.list or not args.board:
        files = list_available()
        print(f"Хранилище: {STORE_DIR}")
        print(f"Файлов: {len(files)}")
        for f in files:
            print(f"  {f.name}")
        return

    # Парсим борд 'AsKsQs' → ['As','Ks','Qs']
    board = [args.board[i:i+2] for i in range(0, len(args.board), 2)]
    cfg = PostflopTreeConfig(
        start_pot_bb=args.pot,
        start_stack_bb=args.stack,
        start_board=board,
        start_street=Street(args.street),
        start_actor="OOP",
    )
    res = load_postflop_strategy(cfg)
    if res is None:
        print(f"Стратегия для борда {args.board} не найдена")
        return
    show(res)


if __name__ == "__main__":
    main()