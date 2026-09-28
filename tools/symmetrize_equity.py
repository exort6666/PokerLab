"""
Симметризация equity таблицы.

Проблема: h1|h2 и h2|h1 пересчитывались независимо, поэтому
их сумма ≠ 1.0. Для каждой пары усредняем и записываем
согласованные значения.

Запуск:
    python tools/symmetrize_equity.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

EQUITY_PATH = Path("data/preflop_equity.json")


def main() -> None:
    if not EQUITY_PATH.exists():
        print(f"Не найдена таблица: {EQUITY_PATH}")
        return

    print(f"Загружаю {EQUITY_PATH} ...", flush=True)
    t0 = time.time()
    data = json.loads(EQUITY_PATH.read_text(encoding="utf-8"))
    print(f"  Загружено {len(data)} пар за {time.time() - t0:.1f} сек",
          flush=True)

    # Собираем уникальные пары
    all_hands = set()
    for key in data:
        h1, h2 = key.split("|")
        all_hands.add(h1)
        all_hands.add(h2)

    all_hands = sorted(all_hands)
    print(f"  Уникальных рук: {len(all_hands)}", flush=True)

    # Симметризация
    print("Симметризую ...", flush=True)
    fixed = 0
    for i, h1 in enumerate(all_hands):
        for h2 in all_hands:
            if h1 == h2:
                continue
            key1 = f"{h1}|{h2}"
            key2 = f"{h2}|{h1}"
            if key1 not in data or key2 not in data:
                continue
            a = data[key1]
            b = 1.0 - data[key2]
            avg = (a + b) / 2.0
            data[key1] = avg
            data[key2] = 1.0 - avg
            if abs(a - avg) > 0.0001:
                fixed += 1

    print(f"  Обработано пар: {len(all_hands) ** 2}", flush=True)
    print(f"  Изменено значений: {fixed}", flush=True)

    # Проверка
    print("Проверка симметрии ...", flush=True)
    max_err = 0.0
    for key, val in data.items():
        h1, h2 = key.split("|")
        rev = f"{h2}|{h1}"
        if rev in data:
            s = val + data[rev]
            max_err = max(max_err, abs(s - 1.0))
    print(f"  Макс. отклонение суммы от 1.0: {max_err:.6f}", flush=True)

    # Бэкап
    backup_path = EQUITY_PATH.with_suffix(".json.bak2")
    if not backup_path.exists():
        backup_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8",
        )
        print(f"  Бэкап: {backup_path}", flush=True)

    # Сохранение
    print(f"Сохраняю {EQUITY_PATH} ...", flush=True)
    EQUITY_PATH.write_text(
        json.dumps(data, indent=2), encoding="utf-8",
    )
    print(f"Готово за {time.time() - t0:.1f} сек", flush=True)


if __name__ == "__main__":
    main()