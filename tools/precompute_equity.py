"""
Предпосчёт preflop equity для всех пар стартовых рук.
Сохраняет результат в data/preflop_equity.json.

Запускать ОДИН РАЗ. Занимает ~45 минут.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from pokerlab.core.cards import Card, Suit
from pokerlab.core.equity import equity
from pokerlab.mtt.pushfold import ALL_HANDS, hand_code_to_cards


OUT_PATH = Path("data/preflop_equity.json")
ITERATIONS = 5000  # точность ~0.7%


def main() -> None:
    out: dict[str, float] = {}
    total = len(ALL_HANDS) * len(ALL_HANDS)
    done = 0
    t0 = time.time()

    for i, h1 in enumerate(ALL_HANDS):
        for h2 in ALL_HANDS:
            key = f"{h1}|{h2}"
            if key in out:
                continue
            # Проверка на пересечение карт
            c1 = hand_code_to_cards(h1)
            c2 = hand_code_to_cards(h2)
            if set(c1) & set(c2):
                out[key] = 0.5  # невозможно, но пусть будет
                done += 1
                continue
            eq = equity(c1, c2, iterations=ITERATIONS, seed=42)
            out[key] = eq
            done += 1

            if done % 100 == 0:
                elapsed = time.time() - t0
                rate = done / elapsed
                remaining = (total - done) / rate
                print(f"  {done}/{total} ({done/total*100:.1f}%) "
                      f"| {rate:.0f} пар/сек | осталось {remaining/60:.1f} мин")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nГотово: {len(out)} пар сохранено в {OUT_PATH}")
    print(f"Время: {(time.time() - t0)/60:.1f} мин")


if __name__ == "__main__":
    main()