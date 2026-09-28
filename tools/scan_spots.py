"""Разведка: какие споты есть в БД Hero."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.db.connection import transaction


def main() -> None:
    with transaction() as conn:
        total = conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
        print(f"Всего раздач: {total}")
        print()

        # 1. Сколько раздач где Hero на префлопе первый вошёл
        # (все до Hero фолд или Hero SB/BTN первый)
        # Ищем: раздачи где Hero сделал префлоп-действие, и до этого не было raise/call
        first_in = conn.execute("""
            SELECT COUNT(DISTINCT h.id)
            FROM hands h
            WHERE EXISTS (
                SELECT 1 FROM actions a
                WHERE a.hand_id = h.id
                  AND a.player_name = 'Hero'
                  AND a.street = 'preflop'
                  AND a.action IN ('fold', 'raise', 'call')
                  AND NOT EXISTS (
                      SELECT 1 FROM actions a2
                      WHERE a2.hand_id = h.id
                        AND a2.street = 'preflop'
                        AND a2.action IN ('call', 'raise')
                        AND a2.action_order < a.action_order
                  )
            )
        """).fetchone()[0]
        print(f"Hero первый вошёл (unopened): {first_in}")

        # 2. Сколько где Hero в BB и был push до него
        bb_vs_push = conn.execute("""
            SELECT COUNT(DISTINCT h.id)
            FROM hands h
            WHERE h.hero_position = 'BB'
              AND EXISTS (
                  SELECT 1 FROM actions a
                  WHERE a.hand_id = h.id
                    AND a.player_name != 'Hero'
                    AND a.street = 'preflop'
                    AND a.action = 'raise'
                    AND a.is_all_in = 1
              )
        """).fetchone()[0]
        print(f"Hero в BB vs push: {bb_vs_push}")

        # 3. Распределение стеков Hero в BB
        print()
        print("Стек Hero в BB по диапазонам:")
        buckets = [
            ("0-10", 0, 10),
            ("10-15", 10, 15),
            ("15-20", 15, 20),
            ("20-30", 20, 30),
            ("30-50", 30, 50),
            ("50+", 50, 10**9),
        ]
        for label, lo, hi in buckets:
            n = conn.execute("""
                SELECT COUNT(*) FROM hands h
                JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
                WHERE CAST(p.stack_start AS REAL) / h.bb >= ?
                  AND CAST(p.stack_start AS REAL) / h.bb < ?
            """, (lo, hi)).fetchone()[0]
            print(f"  {label:>6s} BB: {n:6d}")

        # 4. Сколько раздач где Hero сделал all-in
        hero_push = conn.execute("""
            SELECT COUNT(DISTINCT h.id) FROM hands h
            JOIN actions a ON a.hand_id = h.id
            WHERE a.player_name = 'Hero'
              AND a.street = 'preflop'
              AND a.action = 'raise'
              AND a.is_all_in = 1
        """).fetchone()[0]
        print()
        print(f"Hero сделал all-in префлоп: {hero_push}")

        # 5. Сколько раздач где Hero фолдил префлоп
        hero_fold = conn.execute("""
            SELECT COUNT(DISTINCT h.id) FROM hands h
            WHERE EXISTS (
                SELECT 1 FROM actions a
                WHERE a.hand_id = h.id
                  AND a.player_name = 'Hero'
                  AND a.street = 'preflop'
                  AND a.action = 'fold'
            )
        """).fetchone()[0]
        print(f"Hero фолдил префлоп: {hero_fold}")


if __name__ == "__main__":
    main()