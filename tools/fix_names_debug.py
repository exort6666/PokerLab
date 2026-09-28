"""
Диагностика и фикс имён турниров.

Показывает текущее состояние, читает summary-файлы,
обновляет БД, показывает результат.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.db.connection import transaction
from pokerlab.hh.summary import parse_summary_file

SAMPLE_DIR = Path("data/sample_hh")


def main() -> None:
    print(f"Папка: {SAMPLE_DIR}")
    print(f"Существует: {SAMPLE_DIR.exists()}")
    if not SAMPLE_DIR.exists():
        return

    files = sorted(SAMPLE_DIR.glob("*.txt"))
    print(f"Файлов .txt: {len(files)}")
    print()

    # --- Читаем имена из summary ---
    updates: list[tuple[int, str]] = []
    skipped_hh = 0
    skipped_none = 0

    for f in files:
        try:
            r = parse_summary_file(f)
        except Exception as e:
            print(f"  ERROR: {f.name}: {e}")
            continue

        if r is None:
            skipped_hh += 1
            continue

        if not r.name:
            skipped_none += 1
            continue

        updates.append((r.tournament_id, r.name))

    print(f"Найдено имён из summary: {len(updates)}")
    print(f"Пропущено (не summary / HH): {skipped_hh}")
    print(f"Пропущено (пустое имя): {skipped_none}")
    print()

    # Примеры имён
    print("Примеры из парсера:")
    for tid, name in updates[:5]:
        print(f"  #{tid} → {name}")
    print()

    # --- Текущее состояние БД ---
    print("Проверяю текущее состояние БД ...")
    with transaction() as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM tournaments"
        ).fetchone()[0]
        no_name = conn.execute(
            "SELECT COUNT(*) FROM tournaments WHERE name LIKE 'Tournament #%'"
        ).fetchone()[0]
        print(f"  Всего турниров: {total}")
        print(f"  С заглушкой 'Tournament #': {no_name}")
        print()

        # Проверим первый пример
        if updates:
            tid = updates[0][0]
            row = conn.execute(
                "SELECT name FROM tournaments WHERE id = ?", (tid,)
            ).fetchone()
            if row:
                print(f"  Пример: #{tid} → name='{row[0]}'")
        print()

        # --- Обновление ---
        print("Обновляю имена ...")
        updated = 0
        for tour_id, name in updates:
            row = conn.execute(
                "SELECT name FROM tournaments WHERE id = ?", (tour_id,)
            ).fetchone()
            if row is None:
                continue
            cur = row[0]
            if cur.startswith("Tournament #") and cur != name:
                conn.execute(
                    "UPDATE tournaments SET name = ? WHERE id = ?",
                    (name, tour_id),
                )
                updated += 1
        print(f"  Обновлено: {updated}")
        print()

        # --- Проверка после обновления ---
        no_name_after = conn.execute(
            "SELECT COUNT(*) FROM tournaments WHERE name LIKE 'Tournament #%'"
        ).fetchone()[0]
        print(f"  С заглушкой ПОСЛЕ: {no_name_after}")


if __name__ == "__main__":
    main()