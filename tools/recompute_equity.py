"""
Пересчёт preflop_equity.json через phevaluator.

Два режима:

1. --mode exact
   Точный перебор всех бордов для всех совместимых комбо-пар.
   Точность: 100%. Время: ~25 часов на 12 ядрах.

2. --mode mc --combos N --iters M
   Monte Carlo: N случайных комбо-пар × M итераций бордов.
   Точность: σ ≈ 0.5 / sqrt(N × M). Время: минуты.

Рекомендуется: --mode mc --combos 10 --iters 100000
→ σ = 0.05%, время ~20 минут на 12 ядрах.

Запуск:
    python tools/recompute_equity.py --mode mc --combos 10 --iters 100000
    python tools/recompute_equity.py --mode exact
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from multiprocessing import Pool
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.core.cards import ALL_CARDS, Card
from pokerlab.core.equity_exact import equity_exact
from pokerlab.core.evaluator import evaluate

EQUITY_PATH = Path("data/preflop_equity.json")

RANK_CHARS = "AKQJT98765432"
SUITS = ["h", "d", "c", "s"]


# ============================================================
# 169 стартовых рук
# ============================================================

def _all_hands() -> list[str]:
    out: list[str] = []
    for i, r1 in enumerate(RANK_CHARS):
        out.append(f"{r1}{r1}")
        for r2 in RANK_CHARS[i + 1:]:
            out.append(f"{r1}{r2}s")
            out.append(f"{r1}{r2}o")
    return out


ALL_HANDS = _all_hands()
assert len(ALL_HANDS) == 169


# ============================================================
# Комбо
# ============================================================

def combos(code: str) -> list[tuple[Card, Card]]:
    """Все комбо для кода руки."""
    r1, r2 = code[0], code[1]

    if r1 == r2:
        cs: list[tuple[Card, Card]] = []
        for i, s1 in enumerate(SUITS):
            for s2 in SUITS[i + 1:]:
                cs.append((
                    Card.parse(r1 + s1),
                    Card.parse(r1 + s2),
                ))
        return cs

    if code.endswith("s"):
        return [
            (Card.parse(r1 + s), Card.parse(r2 + s))
            for s in SUITS
        ]

    cs = []
    for s1 in SUITS:
        for s2 in SUITS:
            if s1 != s2:
                cs.append((
                    Card.parse(r1 + s1),
                    Card.parse(r2 + s2),
                ))
    return cs


def compatible(c1: tuple[Card, Card], c2: tuple[Card, Card]) -> bool:
    """Комбо-пары совместимы, если нет общих карт."""
    return not (set(c1) & set(c2))


# ============================================================
# Monte Carlo по бордам для конкретной комбо-пары
# ============================================================

def mc_equity(
    c1: tuple[Card, Card],
    c2: tuple[Card, Card],
    iters: int,
    rng: random.Random,
) -> float:
    """MC equity c1 vs c2. Board = случайные 5 карт из колоды."""
    used = set(c1) | set(c2)
    deck = [c for c in ALL_CARDS if c not in used]
    total = 0.0
    for _ in range(iters):
        board = rng.sample(deck, 5)
        h = evaluate(list(c1) + board)
        v = evaluate(list(c2) + board)
        if h > v:
            total += 1.0
        elif h == v:
            total += 0.5
    return total / iters


# ============================================================
# Обработка одной пары рук
# ============================================================

def process_pair_exact(args: tuple[str, str]) -> tuple[str, str, float]:
    """Точный расчёт: перебор всех бордов для каждой комбо-пары."""
    h1, h2 = args
    cs1 = combos(h1)
    cs2 = combos(h2)
    total = 0.0
    count = 0
    for c1 in cs1:
        for c2 in cs2:
            if not compatible(c1, c2):
                continue
            eq = equity_exact(list(c1), list(c2), [])
            total += eq
            count += 1
    return h1, h2, total / count if count > 0 else 0.5


def process_pair_mc(args: tuple[str, str, int, int]) -> tuple[str, str, float]:
    """MC: сэмплируем комбо-пары, внутри каждой — MC по бордам."""
    h1, h2, n_combos, iters = args
    seed = (hash((h1, h2)) & 0x7FFFFFFF)
    rng = random.Random(seed)
    cs1 = combos(h1)
    cs2 = combos(h2)
    compat = [
        (c1, c2)
        for c1 in cs1
        for c2 in cs2
        if compatible(c1, c2)
    ]
    if not compat:
        return h1, h2, 0.5
    k = min(n_combos, len(compat))
    sampled = rng.sample(compat, k)
    total = 0.0
    for c1, c2 in sampled:
        total += mc_equity(c1, c2, iters, rng)
    return h1, h2, total / k


# ============================================================
# Симметризация
# ============================================================

def symmetrize(data: dict[str, float]) -> None:
    """eq(A,B) + eq(B,A) = 1.0."""
    for h1 in ALL_HANDS:
        for h2 in ALL_HANDS:
            if h1 == h2:
                data[f"{h1}|{h2}"] = 0.5
                continue
            k1 = f"{h1}|{h2}"
            k2 = f"{h2}|{h1}"
            if k1 not in data or k2 not in data:
                continue
            avg = (data[k1] + (1.0 - data[k2])) / 2.0
            data[k1] = avg
            data[k2] = 1.0 - avg


# ============================================================
# Main
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["exact", "mc"], required=True)
    parser.add_argument("--combos", type=int, default=10,
                        help="Сколько комбо-пар сэмплировать (режим mc)")
    parser.add_argument("--iters", type=int, default=100_000,
                        help="MC итераций на комбо-пару (режим mc)")
    parser.add_argument("--workers", type=int, default=12)
    args = parser.parse_args()

    # Бэкап старой таблицы
    if EQUITY_PATH.exists():
        bak = EQUITY_PATH.with_suffix(".json.old")
        if not bak.exists():
            EQUITY_PATH.rename(bak)
            print(f"Старая таблица → {bak}")

    # Все пары (включая диагональ, для совместимости формата)
    pairs: list[tuple] = []
    for h1 in ALL_HANDS:
        for h2 in ALL_HANDS:
            if args.mode == "exact":
                pairs.append((h1, h2))
            else:
                pairs.append((h1, h2, args.combos, args.iters))

    total = len(pairs)
    print(f"Режим: {args.mode}")
    print(f"Пар: {total}")
    print(f"Ядер: {args.workers}")

    if args.mode == "exact":
        est_hours = 25.0
        print(f"Ожидаемое время: ~{est_hours:.1f} часов на 12 ядрах")
    else:
        est_min = (total * args.combos * args.iters) / (12 * 2e6 * 60)
        print(f"Ожидаемое время: ~{est_min:.1f} минут")

    print(flush=True)

    t0 = time.time()
    data: dict[str, float] = {}
    done = 0

    worker_fn = process_pair_exact if args.mode == "exact" else process_pair_mc

    with Pool(args.workers) as pool:
        for h1, h2, eq in pool.imap_unordered(worker_fn, pairs, chunksize=1):
            data[f"{h1}|{h2}"] = eq
            done += 1
            if done % 100 == 0 or done == total:
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                remain = (total - done) / rate if rate > 0 else 0
                print(
                    f"  {done}/{total} ({done/total*100:.1f}%) | "
                    f"{rate:.1f} пар/сек | "
                    f"осталось {remain/60:.1f} мин",
                    flush=True,
                )

    # Симметризация
    print("\nСимметризация ...", flush=True)
    symmetrize(data)

    # Сохранение
    print(f"Сохранение {EQUITY_PATH} ...", flush=True)
    EQUITY_PATH.write_text(
        json.dumps(data, indent=2),
        encoding="utf-8",
    )
    print(f"Готово. Время: {(time.time() - t0) / 60:.1f} мин", flush=True)


if __name__ == "__main__":
    main()