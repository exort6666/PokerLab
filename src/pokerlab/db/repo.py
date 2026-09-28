from __future__ import annotations

import logging
from typing import Iterable

from pokerlab.db.connection import transaction
from pokerlab.hh.models import Hand
from pokerlab.hh.summary import TournamentResult

log = logging.getLogger(__name__)

# Курс юаня к доллару (фиксированный, для воспроизводимости)
CNY_TO_USD_RATE = 0.14


def insert_hand(conn, hand: Hand) -> bool:
    """
    Вставить одну раздачу в БД. conn — открытое соединение.
    Возвращает True, если вставлено, False, если уже была.
    """
    # Проверка: есть ли уже такая раздача?
    row = conn.execute(
        "SELECT 1 FROM hands WHERE id = ? LIMIT 1", (hand.id,)
    ).fetchone()
    if row is not None:
        return False

    # Турнир
    conn.execute("""
        INSERT INTO tournaments (id, name, is_bounty)
        VALUES (?, ?, ?)
        ON CONFLICT(id) DO NOTHING
    """, (
        int(hand.tournament_id),
        hand.tournament_name,
        int("Bounty" in hand.tournament_name),
    ))

    # Раздача
    conn.execute("""
        INSERT INTO hands (
            id, tournament_id, level, sb, bb, ante, table_name,
            button_seat, max_seats, played_at, board, total_pot,
            hero_seat, hero_cards, hero_position, hero_net, raw_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        hand.id,
        int(hand.tournament_id),
        hand.level,
        hand.sb,
        hand.bb,
        hand.ante,
        hand.table_name,
        hand.button_seat,
        hand.max_seats,
        hand.timestamp,
        hand.board,
        hand.total_pot,
        hand.hero_seat,
        hand.hero_cards,
        hand.hero_position,
        hand.hero_net,
        hand.raw_text,
    ))

    # Игроки
    conn.executemany("""
        INSERT INTO hand_players (
            hand_id, seat, name, stack_start, cards, position, is_hero
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        (hand.id, p.seat, p.name, p.stack_start, p.cards,
         p.position, int(p.is_hero))
        for p in hand.players
    ])

    # Действия
    conn.executemany("""
        INSERT INTO actions (
            hand_id, street, action_order, seat, player_name,
            action, amount, amount_to, is_all_in, pot_after
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        (hand.id, a.street, a.order, a.seat, a.player,
         a.action, a.amount, a.amount_to, int(a.is_all_in), a.pot_after)
        for a in hand.actions
    ])

    return True


def insert_many(hands: Iterable[Hand]) -> int:
    """Вставить много раздач. Возвращает количество новых."""
    count = 0
    with transaction() as conn:
        for hand in hands:
            try:
                if insert_hand(conn, hand):
                    count += 1
            except Exception as e:
                log.error("Ошибка при вставке %s: %s", hand.id, e)
    return count


def insert_result(conn, result: TournamentResult) -> bool:
    """
    Вставить результат турнира.
    Если турнира нет в БД — создаёт его с настоящим именем из summary.
    Если турнир есть, но имя — заглушка 'Tournament #ID', обновляет его.
    Конвертирует CNY → USD по фиксированному курсу.
    Возвращает True, если вставлено, False, если уже было.
    """
    # Проверка: уже есть результат?
    row = conn.execute(
        "SELECT 1 FROM tournament_results WHERE tournament_id = ? LIMIT 1",
        (result.tournament_id,),
    ).fetchone()
    if row is not None:
        return False

    # Конвертация валюты
    if result.currency == "CNY":
        rate = CNY_TO_USD_RATE
        buyin = int(round(result.buyin_cents * rate))
        rake = int(round(result.rake_cents * rate))
        bounty = int(round(result.bounty_cents * rate))
        prize_pool = int(round(result.prize_pool_cents * rate))
        payout = int(round(result.hero_payout_cents * rate))
    else:
        buyin = result.buyin_cents
        rake = result.rake_cents
        bounty = result.bounty_cents
        prize_pool = result.prize_pool_cents
        payout = result.hero_payout_cents

    # Имя турнира: если есть в summary — используем, иначе заглушка
    tour_name = result.name if result.name else f"Tournament #{result.tournament_id}"

    # Проверяем, существует ли турнир
    existing = conn.execute(
        "SELECT name FROM tournaments WHERE id = ?",
        (result.tournament_id,),
    ).fetchone()

    if existing is None:
        # Новый турнир — создаём с настоящим именем
        conn.execute("""
            INSERT INTO tournaments (id, name, is_bounty, start_date)
            VALUES (?, ?, ?, ?)
        """, (
            result.tournament_id,
            tour_name,
            int(bounty > 0),
            result.started_at,
        ))
    else:
        # Турнир уже есть. Обновляем имя, если текущее — заглушка.
        cur_name = existing[0]
        if cur_name.startswith("Tournament #"):
            conn.execute(
                "UPDATE tournaments SET name = ? WHERE id = ?",
                (tour_name, result.tournament_id),
            )

    # Результат
    conn.execute("""
        INSERT INTO tournament_results (
            tournament_id, buyin_cents, rake_cents, bounty_cents,
            field_size, prize_pool_cents, hero_place, hero_payout_cents,
            itm, started_at, currency
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result.tournament_id,
        buyin,
        rake,
        bounty,
        result.field_size,
        prize_pool,
        result.hero_place,
        payout,
        int(result.itm),
        result.started_at,
        result.currency,
    ))

    return True


def insert_results_bulk(
    results: list[TournamentResult],
) -> tuple[int, int]:
    """Вставить много результатов. Возвращает (вставлено, пропущено)."""
    inserted = 0
    skipped = 0
    with transaction() as conn:
        for r in results:
            try:
                if insert_result(conn, r):
                    inserted += 1
                else:
                    skipped += 1
            except Exception as e:
                log.error(
                    "Ошибка при вставке результата %s: %s",
                    r.tournament_id, e,
                )
                skipped += 1
    return inserted, skipped


def count_hands() -> int:
    """Сколько раздач в БД."""
    with transaction() as conn:
        row = conn.execute("SELECT COUNT(*) FROM hands").fetchone()
        return int(row[0])


def count_tournaments() -> int:
    """Сколько турниров в БД."""
    with transaction() as conn:
        row = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()
        return int(row[0])


def count_results() -> int:
    """Сколько результатов турниров в БД."""
    with transaction() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM tournament_results"
        ).fetchone()
        return int(row[0])