"""Найти раздачи, которые не классифицировались."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.analysis.spot_classifier import classify_hand
from pokerlab.db.connection import transaction


def main() -> None:
    with transaction() as conn:
        all_hands = conn.execute("""
            SELECT h.id FROM hands h
            WHERE EXISTS (
                SELECT 1 FROM hand_players p
                WHERE p.hand_id = h.id AND p.is_hero = 1
            )
        """).fetchall()

    total = len(all_hands)
    unclassified: list[str] = []
    for row in all_hands:
        if classify_hand(row["id"]) is None:
            unclassified.append(row["id"])

    print(f"Всего с Hero: {total}")
    print(f"Не классифицировано: {len(unclassified)}")
    print()

    # Разбираем 5 примеров
    for hand_id in unclassified[:5]:
        with transaction() as conn:
            hand = conn.execute("""
                SELECT id, tournament_id, level, sb, bb, ante, board,
                       hero_position, hero_cards, total_pot
                FROM hands WHERE id = ?
            """, (hand_id,)).fetchone()

            actions = conn.execute("""
                SELECT action_order, player_name, action, amount,
                       street, is_all_in
                FROM actions WHERE hand_id = ?
                ORDER BY action_order
            """, (hand_id,)).fetchall()

            players = conn.execute("""
                SELECT seat, name, position, stack_start, is_hero
                FROM hand_players WHERE hand_id = ?
                ORDER BY seat
            """, (hand_id,)).fetchall()

        print(f"=== {hand_id} ===")
        print(f"  Hero: {hand['hero_position']} {hand['hero_cards']}, "
              f"bb={hand['bb']}, ante={hand['ante']}")
        print(f"  Игроков: {len(players)}, борд: {hand['board'] or '—'}")
        print(f"  Действия (первые 15):")
        for a in actions[:15]:
            allin = " ALL-IN" if a["is_all_in"] else ""
            print(f"    {a['action_order']:3d} {a['street']:8s} "
                  f"{a['player_name']:12s} {a['action']:12s} "
                  f"amount={a['amount']}{allin}")
        print()


if __name__ == "__main__":
    main()