"""
Одноразовый скрипт: обновляет имена турниров из summary-файлов.

Ситуация: у турниров без HH имя в БД = 'Tournament #ID' (заглушка).
Скрипт читает все summary-файлы в data/sample_hh/, извлекает
настоящее имя, обновляет БД.

Запуск:
    python tools/fix_tournament_names.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.db.connection import transaction
from pokerlab.hh.summary import parse_summary_file

SAMPLE_DIR = Path("data/sample_hh")


def main() -> None:
    if not SAMPLE_DIR.exists():
        print(f"Не найдена папка: {SAMPLE_DIR}")
        return

    files = sorted(SAMPLE_DIR.glob("*.txt"))
    print(f"Найдено файлов: {len(files)}")

    updates: list[tuple[int, str]] = []
    for f in files:
        r = parse_summary_file(f)
        if r is None or not r.name:
            continue
        updates.append((r.tournament_id, r.name))

    print(f"Извлечено имён: {len(updates)}")

    updated = 0
    with transaction() as conn:
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

    print(f"Обновлено имён: {updated}")


if __name__ == "__main__":
    main()