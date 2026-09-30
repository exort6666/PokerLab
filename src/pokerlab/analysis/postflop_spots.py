"""
Извлечение постфлоп-решений Hero из БД (v3).

Fixes:
    * Вложения игрока считаются через diff pot_after (amount у call = 0).
    * eff stack корректно уменьшается по улицам.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pokerlab.db.connection import transaction


class PostflopSpotType(str, Enum):
    SRP = "POSTFLOP_SRP"
    THREE_BET = "POSTFLOP_3BP"
    FOUR_BET = "POSTFLOP_4BP"
    LIMP = "POSTFLOP_LIMP"
    MULTIWAY = "POSTFLOP_MW"
    UNKNOWN = "POSTFLOP_UNK"


@dataclass
class HeroPostflopDecision:
    hand_id: str
    spot_type: PostflopSpotType
    street: str
    hero_position: str
    hero_role: str
    hero_cards: str
    hero_stack_bb: float
    board_full: list[str]
    board_at_decision: list[str]
    pot_bb: float
    pot_at_decision: float
    effective_stack_bb: float
    hero_action: str
    hero_amount_bb: float
    pot_after: float
    num_players_dealt: int
    num_players_postflop: int
    action_order: int


# ============================================================
# Загрузка
# ============================================================

def _load_hand(conn, hand_id):
    row = conn.execute("""
        SELECT h.*, p.stack_start AS hero_stack, p.position AS hero_pos,
               p.cards AS hero_cards
        FROM hands h
        LEFT JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
        WHERE h.id = ?
    """, (hand_id,)).fetchone()
    return dict(row) if row else None


def _load_actions(conn, hand_id):
    rows = conn.execute("""
        SELECT action_order, seat, player_name, action, amount, amount_to,
               is_all_in, street, pot_after
        FROM actions WHERE hand_id = ?
        ORDER BY action_order
    """, (hand_id,)).fetchall()
    return [dict(r) for r in rows]


def _load_players(conn, hand_id):
    rows = conn.execute("""
        SELECT seat, name, stack_start, position, is_hero
        FROM hand_players WHERE hand_id = ?
        ORDER BY seat
    """, (hand_id,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# Утилиты
# ============================================================

def _classify_preflop(preflop_actions):
    n_raises = sum(1 for a in preflop_actions
                   if a["action"] == "raise" and not a["is_all_in"])
    n_allins = sum(1 for a in preflop_actions if a["is_all_in"])
    if n_raises == 0 and n_allins == 0:
        return PostflopSpotType.LIMP
    if n_raises == 1:
        return PostflopSpotType.SRP
    if n_raises == 2:
        return PostflopSpotType.THREE_BET
    if n_raises >= 3:
        return PostflopSpotType.FOUR_BET
    return PostflopSpotType.UNKNOWN


_POS_ORDER = ["UTG", "UTG+1", "UTG+2", "MP", "MP+1",
              "CO", "BTN", "SB", "BB"]


def _is_ip(hero_pos, villain_pos):
    if hero_pos in ("SB", "BB") and villain_pos not in ("SB", "BB"):
        return False
    if villain_pos in ("SB", "BB") and hero_pos not in ("SB", "BB"):
        return True
    if hero_pos in _POS_ORDER and villain_pos in _POS_ORDER:
        return _POS_ORDER.index(hero_pos) > _POS_ORDER.index(villain_pos)
    return False


def _board_cards(s):
    if not s:
        return []
    return [s[i:i+2] for i in range(0, len(s), 2)]


def _board_up_to_street(board_full, street):
    if street == "flop":
        return board_full[:3]
    if street == "turn":
        return board_full[:4]
    if street == "river":
        return board_full[:5]
    return []


def _invested_chips_by_action(
    actions: list[dict],
    player_name: str,
    up_to_order: int,
) -> float:
    """
    Сколько player_name вложил в банк до (не включая) up_to_order.
    Учитываем diff pot_after (amount у call = 0).

    Алгоритм: идём по actions в порядке action_order, отслеживаем
    pot_after. Вложения игрока = pot_after − prev_pot_after, если
    игрок — actor этого действия.
    """
    invested = 0.0
    prev_pot = 0.0
    for a in actions:
        if a["action_order"] >= up_to_order:
            break
        pa = a["pot_after"]
        if pa is None:
            pa = prev_pot
        delta = float(pa) - prev_pot
        if a["player_name"] == player_name and delta > 0:
            invested += delta
        prev_pot = float(pa)
    return invested


# ============================================================
# Основная функция
# ============================================================

def extract_hero_postflop_decisions(hand_id):
    with transaction() as conn:
        hand = _load_hand(conn, hand_id)
        if hand is None or hand["hero_cards"] is None:
            return []
        actions = _load_actions(conn, hand_id)
        players = _load_players(conn, hand_id)

    bb = int(hand["bb"])
    if bb <= 0:
        return []

    preflop = [a for a in actions
               if a["street"] == "preflop"
               and a["action"] not in ("post_ante", "post_sb", "post_bb")]
    postflop = [a for a in actions
                if a["street"] in ("flop", "turn", "river")]
    if not postflop:
        return []

    preflop_folds = {a["player_name"] for a in preflop
                     if a["action"] == "fold"}
    postflop_players = [p for p in players
                        if p["name"] not in preflop_folds]
    n_postflop = len(postflop_players)
    if n_postflop < 2:
        return []

    if n_postflop == 2:
        spot_type = _classify_preflop(preflop)
    else:
        spot_type = PostflopSpotType.MULTIWAY

    villains = [p for p in postflop_players if p["name"] != "Hero"]
    if not villains:
        return []
    villain = villains[0]

    hero_pos = hand["hero_pos"] or "?"
    villain_pos = villain["position"] or "?"
    hero_role = "IP" if _is_ip(hero_pos, villain_pos) else "OOP"

    board_full = _board_cards(hand.get("board") or "")
    hero_stack_chips = float(hand["hero_stack"] or 0)
    villain_stack_chips = float(villain["stack_start"] or 0)

    decisions = []
    for a in postflop:
        if a["player_name"] != "Hero":
            continue
        street = a["street"]
        board_at = _board_up_to_street(board_full, street)
        if len(board_at) < 3:
            continue

        # pot перед действием
        prev_pot_chips = 0.0
        for prev in actions:
            if prev["action_order"] >= a["action_order"]:
                break
            pa = prev["pot_after"]
            if pa is not None and pa > 0:
                prev_pot_chips = float(pa)
        pot_at = prev_pot_chips / bb

        # Вложения игроков — через diff pot_after
        hero_inv = _invested_chips_by_action(
            actions, "Hero", a["action_order"])
        villain_inv = _invested_chips_by_action(
            actions, villain["name"], a["action_order"])

        hero_rem_bb = (hero_stack_chips - hero_inv) / bb
        villain_rem_bb = (villain_stack_chips - villain_inv) / bb
        eff_bb = min(hero_rem_bb, villain_rem_bb)

        decisions.append(HeroPostflopDecision(
            hand_id=hand_id,
            spot_type=spot_type,
            street=street,
            hero_position=hero_pos,
            hero_role=hero_role,
            hero_cards=hand["hero_cards"],
            hero_stack_bb=round(hero_stack_chips / bb, 2),
            board_full=board_full,
            board_at_decision=board_at,
            pot_bb=round(pot_at, 2),
            pot_at_decision=round(pot_at, 2),
            effective_stack_bb=round(eff_bb, 2),
            hero_action=a["action"],
            hero_amount_bb=round((a["amount"] or 0) / bb, 2),
            pot_after=round((a["pot_after"] or 0) / bb, 2),
            num_players_dealt=len(players),
            num_players_postflop=n_postflop,
            action_order=a["action_order"],
        ))
    return decisions


def extract_all(limit=None, hu_only=True):
    with transaction() as conn:
        rows = conn.execute("""
            SELECT h.id FROM hands h
            WHERE EXISTS (
                SELECT 1 FROM hand_players p
                WHERE p.hand_id = h.id AND p.is_hero = 1
            )
            ORDER BY h.played_at DESC
        """).fetchall()
    if limit:
        rows = rows[:limit]
    out = []
    for row in rows:
        for d in extract_hero_postflop_decisions(row["id"]):
            if hu_only and d.num_players_postflop != 2:
                continue
            out.append(d)
    return out


if __name__ == "__main__":
    import sys
    from collections import Counter

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    print(f"Загружаю до {limit} раздач...")
    decisions = extract_all(limit=limit, hu_only=True)
    print(f"Извлечено: {len(decisions)}\n")

    by_spot = Counter(d.spot_type.value for d in decisions)
    by_street = Counter(d.street for d in decisions)
    by_role = Counter(d.hero_role for d in decisions)

    print("По споту:")
    for k, v in by_spot.most_common():
        print(f"  {k:>20}: {v}")
    print("\nПо улице:")
    for k, v in by_street.most_common():
        print(f"  {k:>8}: {v}")
    print("\nПо роли:")
    for k, v in by_role.most_common():
        print(f"  {k:>5}: {v}\n")

    buckets = [(0, 10), (10, 15), (15, 20), (20, 30), (30, 50),
               (50, 75), (75, 100), (100, 999)]
    print("Eff stack:")
    for lo, hi in buckets:
        n = sum(1 for d in decisions if lo <= d.effective_stack_bb < hi)
        print(f"  {lo:>3}–{hi:<3} BB: {n}")

    print("\nPot на флопе:")
    for lo, hi in [(0, 5), (5, 10), (10, 20), (20, 40), (40, 999)]:
        n = sum(1 for d in decisions
                if d.street == "flop" and lo <= d.pot_at_decision < hi)
        print(f"  {lo:>3}–{hi:<3} BB: {n}")

    print("\nПримеры:")
    for d in decisions[:10]:
        board_str = "".join(d.board_at_decision)
        print(f"  {d.hand_id[:12]} | {d.spot_type.value[9:]} | "
              f"{d.street:>5} | {d.hero_role} | {d.hero_cards} | "
              f"board={board_str} | pot={d.pot_at_decision} | "
              f"eff={d.effective_stack_bb} | {d.hero_action}")