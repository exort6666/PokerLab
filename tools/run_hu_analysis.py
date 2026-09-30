"""
Пакетный расчёт HU push/fold спотов (chipEV).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.db.connection import transaction
from pokerlab.mtt.hu_solver import cards_to_code, solve_hu_chipEV


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


def _load_hand_data(conn, hand_id: str) -> dict | None:
    hand = conn.execute("""
        SELECT h.*, p.stack_start AS hero_stack, p.position AS hero_pos,
               p.cards AS hero_cards
        FROM hands h
        LEFT JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
        WHERE h.id = ?
    """, (hand_id,)).fetchone()
    if hand is None:
        return None

    actions = conn.execute("""
        SELECT action_order, player_name, action, amount, amount_to,
               is_all_in, street, pot_after
        FROM actions WHERE hand_id = ?
        ORDER BY action_order
    """, (hand_id,)).fetchall()

    players = conn.execute("""
        SELECT seat, name, stack_start, position, is_hero
        FROM hand_players WHERE hand_id = ?
        ORDER BY seat
    """, (hand_id,)).fetchall()

    return {
        "hand": dict(hand),
        "actions": [dict(a) for a in actions],
        "players": [dict(p) for p in players],
    }


def _invested_before(actions: list[dict], name: str, before_order: int) -> int:
    return sum(
        a["amount"] for a in actions
        if a["player_name"] == name
        and a["action_order"] < before_order
        and a["action"] in ("post_ante", "post_sb", "post_bb", "call", "raise")
    )


def evaluate_hu_spot(hand_id: str) -> dict | None:
    with transaction() as conn:
        data = _load_hand_data(conn, hand_id)
    if data is None:
        return None

    hand = data["hand"]
    actions = data["actions"]
    players = data["players"]

    bb = hand["bb"]
    if not bb:
        return None

    preflop_decisions = [
        a for a in actions
        if a["street"] == "preflop"
        and a["action"] not in ("post_ante", "post_sb", "post_bb")
    ]

    # Найти push
    push_idx = None
    for i, a in enumerate(preflop_decisions):
        if a["action"] == "raise" and a["is_all_in"]:
            push_idx = i
            break
    if push_idx is None:
        return None

    pusher_name = preflop_decisions[push_idx]["player_name"]
    push_order = preflop_decisions[push_idx]["action_order"]
    hero_is_pusher = pusher_name == "Hero"

    # Ровно 2 игрока вложили (call или raise)
    active_investors = {
        a["player_name"] for a in preflop_decisions
        if a["action"] in ("call", "raise")
    }
    active_investors.add(pusher_name)

    if len(active_investors) != 2:
        return None

    opponent_name = next(
        (p for p in active_investors if p != "Hero"), None
    )
    if opponent_name is None or "Hero" not in active_investors:
        return None

    # Определить действие Hero
    if hero_is_pusher:
        hero_action = "push"
    else:
        hero_decision = None
        for i in range(push_idx + 1, len(preflop_decisions)):
            if preflop_decisions[i]["player_name"] == "Hero":
                hero_decision = preflop_decisions[i]
                break
        if hero_decision is None:
            return None
        # Между push и Hero — только fold
        for i in range(push_idx + 1, len(preflop_decisions)):
            if preflop_decisions[i] is hero_decision:
                break
            if preflop_decisions[i]["action"] != "fold":
                return None
        # Hero call, репуш или изоляционный рейз — эквивалентны
        if hero_decision["action"] == "fold":
            hero_action = "fold"
        else:
            hero_action = "call"

    # Стеки
    hero_stack_start = next(
        (p["stack_start"] for p in players if p["name"] == "Hero"), None
    )
    opp_stack_start = next(
        (p["stack_start"] for p in players if p["name"] == opponent_name), None
    )
    if hero_stack_start is None or opp_stack_start is None:
        return None

    # Вклады
    hero_inv = _invested_before(actions, "Hero", push_order)
    opp_inv = _invested_before(actions, opponent_name, push_order)

    # pot_before_push — реальный pot до push, включая ante/sb/bb
    pot_before_push = 0
    for a in actions:
        if a["action_order"] >= push_order:
            break
        pa = a["pot_after"]
        if pa is not None and pa > 0:
            pot_before_push = pa

    dead_money_chips = max(0, pot_before_push - hero_inv - opp_inv)

    # Роли
    if hero_is_pusher:
        pusher_stack = hero_stack_start
        caller_stack = opp_stack_start
        pusher_inv = hero_inv
        caller_inv = opp_inv
    else:
        pusher_stack = opp_stack_start
        caller_stack = hero_stack_start
        pusher_inv = opp_inv
        caller_inv = hero_inv

    # Все стеки в BB
    pusher_start_bb = pusher_stack / bb
    caller_start_bb = caller_stack / bb
    pusher_inv_bb = pusher_inv / bb
    caller_inv_bb = caller_inv / bb
    dead_money_bb = dead_money_chips / bb

    # Отсеиваем невозможные данные
    if pusher_start_bb <= 0 or caller_start_bb <= 0:
        return None

    # Остаток стека
    pusher_remaining = pusher_start_bb - pusher_inv_bb
    caller_remaining = caller_start_bb - caller_inv_bb
    if pusher_remaining <= 0 or caller_remaining <= 0:
        return None

    result = solve_hu_chipEV(
        pusher_start_bb=pusher_start_bb,
        caller_start_bb=caller_start_bb,
        pusher_inv_bb=pusher_inv_bb,
        caller_inv_bb=caller_inv_bb,
        dead_money_bb=dead_money_bb,
        iterations=2000,
    )

    hero_code = cards_to_code(hand["hero_cards"] or "")
    if hero_code is None:
        return None

    # optimal_action — по-прежнему из диапазона (порог >0.5),
    # чтобы is_correct оставался консистентен с тем, что уже в БД
    # и что рисует RangeCanvas.
    if hero_is_pusher:
        optimal = "push" if hero_code in result.push_range else "fold"
        spot_type = "PREFLOP_HERO_PUSH"
    else:
        optimal = "call" if hero_code in result.call_range else "fold"
        spot_type = "PREFLOP_VS_PUSH"

    # --- EV ---
    # Для Hero-пушера: EV(push) = result.ev_push[hero_code],
    #                  EV(fold) = result.ev_fold_pusher.
    # Для Hero-коллера: EV(call) = result.ev_call[hero_code],
    #                   EV(fold) = result.ev_fold_caller.
    if hero_is_pusher:
        ev_push_h = result.ev_push.get(hero_code)
        ev_fold_h = result.ev_fold_pusher
        ev_actual = ev_push_h if hero_action == "push" else ev_fold_h
        ev_optimal = ev_push_h if optimal == "push" else ev_fold_h
    else:
        ev_call_h = result.ev_call.get(hero_code)
        ev_fold_h = result.ev_fold_caller
        ev_actual = ev_call_h if hero_action == "call" else ev_fold_h
        ev_optimal = ev_call_h if optimal == "call" else ev_fold_h

    if ev_actual is not None and ev_optimal is not None:
        ev_loss = ev_optimal - ev_actual
        # Численный шум: у правильного решения loss должен быть ровно 0
        if hero_action == optimal and ev_loss < 0:
            ev_loss = 0.0
    else:
        ev_loss = None

    return {
        "hand_id": hand_id,
        "spot_type": spot_type,
        "hero_action": hero_action,
        "optimal_action": optimal,
        "is_correct": hero_action == optimal,
        "hero_code": hero_code,
        "pusher_start_bb": round(pusher_start_bb, 2),
        "caller_start_bb": round(caller_start_bb, 2),
        "pusher_inv_bb": round(pusher_inv_bb, 2),
        "caller_inv_bb": round(caller_inv_bb, 2),
        "dead_money_bb": round(dead_money_bb, 2),
        "push_freq": result.push_freq,
        "call_freq": result.call_freq,
        "ev_optimal": ev_optimal,
        "ev_actual": ev_actual,
        "ev_loss": ev_loss,
    }


def save_result(r: dict) -> None:
    details = {
        "hero_code": r["hero_code"],
        "pusher_start_bb": r["pusher_start_bb"],
        "caller_start_bb": r["caller_start_bb"],
        "pusher_inv_bb": r["pusher_inv_bb"],
        "caller_inv_bb": r["caller_inv_bb"],
        "dead_money_bb": r["dead_money_bb"],
        "push_freq": r["push_freq"],
        "call_freq": r["call_freq"],
    }
    with transaction() as conn:
        conn.execute("""
            INSERT INTO hand_analysis (
                hand_id, spot_type, street, solver_name, solver_version,
                hero_action, optimal_action, ev_optimal, ev_actual, ev_loss,
                is_correct, is_critical, details
            ) VALUES (?, ?, 'preflop', 'hu_solver_chipEV', 'v1.4',
                      ?, ?, ?, ?, ?, ?, 0, ?)
            ON CONFLICT(hand_id) DO UPDATE SET
                spot_type = excluded.spot_type,
                solver_name = 'hu_solver_chipEV',
                solver_version = 'v1.4',
                hero_action = excluded.hero_action,
                optimal_action = excluded.optimal_action,
                ev_optimal = excluded.ev_optimal,
                ev_actual = excluded.ev_actual,
                ev_loss = excluded.ev_loss,
                is_correct = excluded.is_correct,
                details = excluded.details,
                computed_at = datetime('now')
        """, (
            r["hand_id"], r["spot_type"], r["hero_action"], r["optimal_action"],
            r.get("ev_optimal"), r.get("ev_actual"), r.get("ev_loss"),
            int(r["is_correct"]), json.dumps(details, ensure_ascii=False),
        ))


def main() -> None:
    log.info("Загружаю список спотов...")
    with transaction() as conn:
        rows = conn.execute("""
            SELECT hand_id FROM hand_analysis
            WHERE spot_type IN ('PREFLOP_VS_PUSH', 'PREFLOP_HERO_PUSH')
            ORDER BY hand_id
        """).fetchall()

    total = len(rows)
    log.info("Всего спотов: %d", total)

    t0 = time.time()
    ok = skipped = errors = 0

    for i, row in enumerate(rows, 1):
        hand_id = row["hand_id"]
        try:
            r = evaluate_hu_spot(hand_id)
            if r is None:
                skipped += 1
            else:
                save_result(r)
                ok += 1
        except Exception as e:
            errors += 1
            log.error("Ошибка %s: %s", hand_id, e)

        if i % 100 == 0 or i == total:
            elapsed = time.time() - t0
            rate = i / elapsed if elapsed > 0 else 0
            remain = (total - i) / rate / 60 if rate > 0 else 0
            log.info(
                "  %d/%d | ok=%d skipped=%d errors=%d | "
                "%.1f/сек | осталось %.1f мин",
                i, total, ok, skipped, errors, rate, remain,
            )

    log.info("ГОТОВО. Всего: %d. Успешно: %d. Пропущено: %d. Ошибок: %d.",
             total, ok, skipped, errors)


if __name__ == "__main__":
    main()