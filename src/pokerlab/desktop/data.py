"""Загрузка данных из БД."""

from __future__ import annotations

import sqlite3

from pokerlab.config import DB_PATH


def load_tournaments_with_hands() -> list[dict]:
    """
    Загружает HU-раздачи, сгруппированные по турнирам.
    Возвращает список турниров, у каждого — вложенный список раздач.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("""
        SELECT
            a.hand_id,
            a.spot_type,
            a.hero_action,
            a.optimal_action,
            a.details,
            a.is_correct,
            a.ev_optimal,
            a.ev_actual,
            a.ev_loss,
            h.tournament_id,
            h.played_at,
            t.name AS tournament_name,
            t.is_bounty AS is_bounty,
            tr.started_at AS tournament_date,
            hp.position AS hero_position
        FROM hand_analysis a
        JOIN hands h ON h.id = a.hand_id
        LEFT JOIN tournaments t ON t.id = h.tournament_id
        LEFT JOIN tournament_results tr ON tr.tournament_id = h.tournament_id
        LEFT JOIN hand_players hp
            ON hp.hand_id = a.hand_id AND hp.is_hero = 1
        WHERE a.solver_name = 'hu_solver_chipEV'
        ORDER BY h.tournament_id, h.played_at
    """).fetchall()
    conn.close()

    # Группировка
    tournaments: dict[int, dict] = {}
    for r in rows:
        tid = r["tournament_id"]
        if tid not in tournaments:
            tournaments[tid] = {
                "tournament_id": tid,
                "tournament_name": r["tournament_name"] or f"Tournament #{tid}",
                "tournament_date": r["tournament_date"],
                "is_bounty": bool(r["is_bounty"]),
                "hands": [],
                "hands_count": 0,
                "errors_count": 0,
            }
        t = tournaments[tid]
        t["hands"].append(dict(r))
        t["hands_count"] += 1
        if not r["is_correct"]:
            t["errors_count"] += 1

    # Сортировка турниров: сначала с ошибками, потом по дате (свежие сверху)
    result = list(tournaments.values())
    result.sort(
        key=lambda x: (
            -x["errors_count"],
            -(int(x["tournament_date"].replace("/", "").replace(":", "").replace(" ", "").replace("-", "")[:8])
              if x["tournament_date"] else 0),
        )
    )
    return result


def load_hand_full(hand_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    hand = dict(conn.execute("""
        SELECT h.*,
               t.name AS tournament_name,
               t.is_bounty AS is_bounty,
               tr.started_at AS tournament_date,
               (tr.buyin_cents + tr.rake_cents + tr.bounty_cents) AS total_buyin_cents,
               tr.bounty_cents AS start_bounty_cents
        FROM hands h
        LEFT JOIN tournaments t ON t.id = h.tournament_id
        LEFT JOIN tournament_results tr ON tr.tournament_id = h.tournament_id
        WHERE h.id = ?
    """, (hand_id,)).fetchone())
    players = [dict(r) for r in conn.execute(
        "SELECT * FROM hand_players WHERE hand_id = ? ORDER BY seat",
        (hand_id,),
    ).fetchall()]
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM actions WHERE hand_id = ? ORDER BY action_order",
        (hand_id,),
    ).fetchall()]
    bounty = conn.execute(
        "SELECT hero_bounty, villain_bounty FROM hand_bounty WHERE hand_id = ?",
        (hand_id,),
    ).fetchone()
    conn.close()
    return {
        "hand": hand,
        "players": players,
        "actions": actions,
        "bounty": dict(bounty) if bounty else None,
    }


def save_bounty(hand_id: str, hero_bounty: float, villain_bounty: float) -> None:
    """Сохранить/обновить баунти для руки. Только для bounty-турниров."""
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("""
        SELECT t.is_bounty
        FROM hands h
        JOIN tournaments t ON t.id = h.tournament_id
        WHERE h.id = ?
    """, (hand_id,)).fetchone()
    if row is None or not row[0]:
        conn.close()
        raise ValueError("Не bounty-турнир — баунти не сохраняются")

    conn.execute("""
        INSERT INTO hand_bounty (hand_id, hero_bounty, villain_bounty, source)
        VALUES (?, ?, ?, 'manual')
        ON CONFLICT(hand_id) DO UPDATE SET
            hero_bounty = excluded.hero_bounty,
            villain_bounty = excluded.villain_bounty,
            updated_at = datetime('now')
    """, (hand_id, hero_bounty, villain_bounty))
    conn.commit()
    conn.close()


def delete_bounty(hand_id: str) -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM hand_bounty WHERE hand_id = ?", (hand_id,))
    conn.commit()
    conn.close()