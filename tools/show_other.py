"""
Показать турниры, которые попадают в категорию 'Other'.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.analysis.classify import classify_type
from pokerlab.db.connection import transaction


def main() -> None:
    with transaction() as conn:
        rows = conn.execute("""
            SELECT DISTINCT t.name
            FROM tournaments t
            JOIN tournament_results r ON r.tournament_id = t.id
            WHERE r.currency != 'SAT'
              AND r.buyin_cents + r.rake_cents + r.bounty_cents > 0
            ORDER BY t.name
        """).fetchall()

    other_names: list[str] = []
    for row in rows:
        name = row[0]
        if classify_type(name) == "Other":
            other_names.append(name)

    print(f"Всего уникальных имён в Other: {len(other_names)}")
    print()
    for name in other_names:
        print(f"  {name}")


if __name__ == "__main__":
    main()