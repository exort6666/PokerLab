"""
Исправление предпосчитанной equity таблицы.

Проблема: для пар с пересекающимися картами (например, AA vs AKo)
сохранено значение 0.5. Реальные значения — 60-95%.

Решение: для каждой сломанной пары пересчитать equity,
усредняя по НЕСКОЛЬКИМ случайным совместимым комбо-парам.

Запуск:
    python tools/fix_equity_table.py
"""

from __future__ import annotations

import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.core.cards import Card
from pokerlab.core.equity import equity

EQUITY_PATH = Path("data/preflop_equity.json")
ITERATIONS = 500        # Monte Carlo итераций на одну комбо-пару
SAMPLES = 3             # сколько комбо-пар сэмплировать
RNG_SEED = 42


# ============================================================
# Все 169 рук и их комбо
# ============================================================

RANK_CHARS = "AKQJT98765432"
SUITS = ["h", "d", "c", "s"]


def build_all_hands() -> list[str]:
    hands: list[str] = []
    for i, r1 in enumerate(RANK_CHARS):
        hands.append(f"{r1}{r1}")
        for r2 in RANK_CHARS[i + 1:]:
            hands.append(f"{r1}{r2}s")
            hands.append(f"{r1}{r2}o")
    return hands


ALL_HANDS = build_all_hands()
assert len(ALL_HANDS) == 169


def hand_code_to_combos(code: str) -> list[tuple[Card, Card]]:
    """Все комбо для кода руки."""
    r1, r2 = code[0], code[1]

    if r1 == r2:
        combos: list[tuple[Card, Card]] = []
        for i, s1 in enumerate(SUITS):
            for s2 in SUITS[i + 1:]:
                combos.append((
                    Card.parse(r1 + s1),
                    Card.parse(r1 + s2),
                ))
        return combos

    if code.endswith("s"):
        return [
            (Card.parse(r1 + s), Card.parse(r2 + s))
            for s in SUITS
        ]

    combos = []
    for s1 in SUITS:
        for s2 in SUITS:
            if s1 != s2:
                combos.append((
                    Card.parse(r1 + s1),
                    Card.parse(r2 + s2),
                ))
    return combos


def representative_combo(code: str) -> tuple[Card, Card]:
    """Один representative комбо — так же, как в precompute."""
    r1, r2 = code[0], code[1]
    rank_value = {c: 14 - i for i, c in enumerate(RANK_CHARS)}
    v1, v2 = rank_value[r1], rank_value[r2]

    if r1 == r2:
        return Card(v1, 2), Card(v1, 3)  # Hearts, Diamonds
    if code.endswith("s"):
        return Card(v1, 2), Card(v2, 2)  # Hearts
    return Card(v1, 2), Card(v2, 3)      # Hearts, Diamonds


def is_broken(h1: str, h2: str) -> bool:
    """Сломана, если representative комбо пересекаются."""
    c1 = representative_combo(h1)
    c2 = representative_combo(h2)
    return c1[0] in c2 or c1[1] in c2


# ============================================================
# Пересчёт одной пары
# ============================================================

def fix_one_pair(args: tuple[str, str]) -> tuple[str, str, float]:
    """Пересчитать equity пары рук — усреднение по SAMPLES комбо-парам."""
    h1, h2 = args
    rng = random.Random(RNG_SEED + hash((h1, h2)) % 10000)

    combos1 = hand_code_to_combos(h1)
    combos2 = hand_code_to_combos(h2)

    # Найти все совместимые комбо-пары
    compatible: list[tuple[tuple[Card, Card], tuple[Card, Card]]] = []
    for c1 in combos1:
        for c2 in combos2:
            if c1[0] in c2 or c1[1] in c2:
                continue
            compatible.append((c1, c2))

    if not compatible:
        return h1, h2, 0.5

    # Сэмплировать SAMPLES штук
    if len(compatible) <= SAMPLES:
        sample = compatible
    else:
        sample = rng.sample(compatible, SAMPLES)

    total = 0.0
    for c1, c2 in sample:
        total += equity(list(c1), list(c2), iterations=ITERATIONS,
                        seed=rng.randint(0, 10**9))

    return h1, h2, total / len(sample)


# ============================================================
# Main
# ============================================================

def main() -> None:
    if not EQUITY_PATH.exists():
        print(f"Не найдена таблица: {EQUITY_PATH}")
        return

    print(f"Загружаю {EQUITY_PATH} ...", flush=True)
    t0 = time.time()
    data = json.loads(EQUITY_PATH.read_text(encoding="utf-8"))
    print(f"  Загружено {len(data)} пар за {time.time() - t0:.1f} сек",
          flush=True)

    print("Ищу сломанные пары ...", flush=True)
    broken: list[tuple[str, str]] = []
    for h1 in ALL_HANDS:
        for h2 in ALL_HANDS:
            if is_broken(h1, h2):
                broken.append((h1, h2))

    print(f"  Найдено: {len(broken)} пар", flush=True)
    if not broken:
        print("Нечего исправлять.", flush=True)
        return

    # Бэкап
    backup_path = EQUITY_PATH.with_suffix(".json.bak")
    if not backup_path.exists():
        backup_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8",
        )
        print(f"  Бэкап: {backup_path}", flush=True)

    n_workers = 12
    print(f"Запускаю на {n_workers} ядрах, "
          f"{ITERATIONS} iter × {SAMPLES} sample на пару ...", flush=True)

    t0 = time.time()
    done = 0
    with Pool(n_workers) as pool:
        for h1, h2, eq in pool.imap_unordered(
            fix_one_pair, broken, chunksize=1
        ):
            data[f"{h1}|{h2}"] = eq
            done += 1
            if done % 20 == 0 or done == 1:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                remaining = (len(broken) - done) / rate if rate > 0 else 0
                print(
                    f"  {done}/{len(broken)} "
                    f"({done/len(broken)*100:.1f}%) | "
                    f"{rate:.1f} пар/сек | "
                    f"осталось {remaining/60:.1f} мин",
                    flush=True,
                )

    print(f"\nСохраняю {EQUITY_PATH} ...", flush=True)
    EQUITY_PATH.write_text(
        json.dumps(data, indent=2), encoding="utf-8",
    )
    print(f"Готово. Время: {(time.time() - t0)/60:.1f} мин", flush=True)


if __name__ == "__main__":
    main()