"""
Классификатор покерных спотов.

Определяет тип спота в раздаче: PREFLOP_VS_PUSH, PREFLOP_OPEN, POSTFLOP_SRP, ...
Это определяет, какой solver применять для оценки Hero-решения.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from pokerlab.db.connection import transaction


class SpotType(str, Enum):
    """Тип спота — определяет solver."""
    PREFLOP_HERO_PUSH = "PREFLOP_HERO_PUSH"
    PREFLOP_VS_PUSH = "PREFLOP_VS_PUSH"
    PREFLOP_OPEN = "PREFLOP_OPEN"
    PREFLOP_VS_OPEN = "PREFLOP_VS_OPEN"
    PREFLOP_3BET = "PREFLOP_3BET"
    PREFLOP_VS_3BET = "PREFLOP_VS_3BET"
    POSTFLOP_SRP = "POSTFLOP_SRP"
    POSTFLOP_3BP = "POSTFLOP_3BP"
    POSTFLOP_4BP = "POSTFLOP_4BP"
    POSTFLOP_LIMP = "POSTFLOP_LIMP"
    MULTIWAY = "MULTIWAY"
    UNKNOWN = "UNKNOWN"


@dataclass
class HeroAction:
    """Действие Hero в споте."""
    order: int
    action: str
    amount: int
    amount_to: int
    is_all_in: bool


@dataclass
class SpotInfo:
    """Информация о споте."""
    hand_id: str
    spot_type: SpotType
    street: str
    hero_position: str
    hero_cards: str
    hero_stack_bb: float
    bb: int

    num_players_dealt: int
    num_players_active: int
    num_players_postflop: int

    action_history: list[dict] = field(default_factory=list)
    hero_action: HeroAction | None = None
    actions_after_hero: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "hand_id": self.hand_id,
            "spot_type": self.spot_type.value,
            "street": self.street,
            "hero_position": self.hero_position,
            "hero_cards": self.hero_cards,
            "hero_stack_bb": self.hero_stack_bb,
            "bb": self.bb,
            "num_players_dealt": self.num_players_dealt,
            "num_players_active": self.num_players_active,
            "num_players_postflop": self.num_players_postflop,
            "hero_action": self.hero_action.action if self.hero_action else None,
            "num_actions_before": len(self.action_history),
            "num_actions_after": len(self.actions_after_hero),
        }


# ============================================================
# Загрузка данных раздачи
# ============================================================

def _load_hand(conn, hand_id: str) -> dict | None:
    row = conn.execute("""
        SELECT h.*, p.stack_start AS hero_stack, p.position AS hp, p.cards AS hc
        FROM hands h
        LEFT JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
        WHERE h.id = ?
    """, (hand_id,)).fetchone()
    return dict(row) if row else None


def _load_actions(conn, hand_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT action_order, seat, player_name, action, amount, amount_to,
               is_all_in, street, pot_after
        FROM actions WHERE hand_id = ?
        ORDER BY action_order
    """, (hand_id,)).fetchall()
    return [dict(r) for r in rows]


def _load_players(conn, hand_id: str) -> list[dict]:
    rows = conn.execute("""
        SELECT seat, name, stack_start, position, is_hero
        FROM hand_players WHERE hand_id = ?
        ORDER BY seat
    """, (hand_id,)).fetchall()
    return [dict(r) for r in rows]


# ============================================================
# Классификатор
# ============================================================

def classify_hand(hand_id: str) -> SpotInfo | None:
    """
    Классифицировать раздачу. Возвращает SpotInfo или None,
    если Hero не участвовал или спот не распознан.
    """
    with transaction() as conn:
        hand = _load_hand(conn, hand_id)
        if hand is None or hand["hero_stack"] is None:
            return None

        actions = _load_actions(conn, hand_id)
        players = _load_players(conn, hand_id)

    # Метаданные
    bb = int(hand["bb"])
    hero_stack_bb = hand["hero_stack"] / bb if bb > 0 else 0
    hero_position = hand["hp"] or "?"
    hero_cards = hand["hc"] or "?"

    num_players_dealt = len(players)

    # Разбор действий на префлопе
    # Исключаем post_ante / post_sb / post_bb — это НЕ "решения"
    preflop_actions = [
        a for a in actions
        if a["street"] == "preflop"
        and a["action"] not in ("post_ante", "post_sb", "post_bb")
    ]

    # Первое РЕШЕНИЕ Hero на префлопе
    hero_preflop_idx = None
    for i, a in enumerate(preflop_actions):
        if a["player_name"] == "Hero":
            hero_preflop_idx = i
            break

    if hero_preflop_idx is None:
        return None

    hero_action_raw = preflop_actions[hero_preflop_idx]
    actions_before_hero = preflop_actions[:hero_preflop_idx]
    actions_after_hero = preflop_actions[hero_preflop_idx + 1:]

    hero_action = HeroAction(
        order=hero_action_raw["action_order"],
        action=hero_action_raw["action"],
        amount=hero_action_raw["amount"],
        amount_to=hero_action_raw["amount_to"],
        is_all_in=bool(hero_action_raw["is_all_in"]),
    )

    # Активные игроки до Hero
    folded_before = {a["player_name"] for a in actions_before_hero
                     if a["action"] == "fold"}
    num_players_active = num_players_dealt - len(folded_before)

    # Постфлоп
    all_postflop_actions = [
        a for a in actions if a["street"] in ("flop", "turn", "river")
    ]
    num_players_postflop = 0
    if all_postflop_actions:
        folded_preflop = {a["player_name"] for a in preflop_actions
                          if a["action"] == "fold"}
        num_players_postflop = num_players_dealt - len(folded_preflop)

    # Raise / call / push до Hero
    raise_before_hero = [
        a for a in actions_before_hero if a["action"] == "raise"
    ]
    call_before_hero = [
        a for a in actions_before_hero if a["action"] == "call"
    ]
    push_before_hero = [
        a for a in raise_before_hero if a["is_all_in"]
    ]

    # === Определение типа спота ===

    # Проверяем, действовал ли Hero постфлоп.
    # Если Hero сфолдил префлоп и не действовал постфлоп — классифицируем
    # по префлопу (важно для раздач где Hero сфолдил префлоп).
    hero_acted_postflop = any(
        a["player_name"] == "Hero" for a in all_postflop_actions
    )

    if all_postflop_actions and hero_acted_postflop:
        # Найти первое решение Hero постфлоп
        postflop_hero_idx = None
        for i, a in enumerate(all_postflop_actions):
            if a["player_name"] == "Hero":
                postflop_hero_idx = i
                break

        postflop_hero_action = all_postflop_actions[postflop_hero_idx]
        street = postflop_hero_action["street"]

        # Классификация постфлопа
        if num_players_postflop > 2:
            spot_type = SpotType.MULTIWAY
        else:
            n_raises_preflop = len(raise_before_hero)
            if n_raises_preflop >= 2:
                spot_type = SpotType.POSTFLOP_4BP
            elif n_raises_preflop == 1:
                spot_type = SpotType.POSTFLOP_3BP
            elif call_before_hero:
                spot_type = SpotType.POSTFLOP_SRP
            else:
                spot_type = SpotType.POSTFLOP_LIMP

        return SpotInfo(
            hand_id=hand_id,
            spot_type=spot_type,
            street=street,
            hero_position=hero_position,
            hero_cards=hero_cards,
            hero_stack_bb=round(hero_stack_bb, 1),
            bb=bb,
            num_players_dealt=num_players_dealt,
            num_players_active=num_players_active,
            num_players_postflop=num_players_postflop,
            action_history=all_postflop_actions[:postflop_hero_idx],
            hero_action=HeroAction(
                order=postflop_hero_action["action_order"],
                action=postflop_hero_action["action"],
                amount=postflop_hero_action["amount"],
                amount_to=postflop_hero_action["amount_to"],
                is_all_in=bool(postflop_hero_action["is_all_in"]),
            ),
            actions_after_hero=all_postflop_actions[postflop_hero_idx + 1:],
        )

    # === Префлоп-споты (без постфлопа или Hero не действовал постфлоп) ===
    if hero_action.is_all_in and hero_action.action == "raise":
        spot_type = SpotType.PREFLOP_HERO_PUSH
    elif push_before_hero:
        spot_type = SpotType.PREFLOP_VS_PUSH
    elif len(raise_before_hero) >= 2:
        spot_type = SpotType.PREFLOP_VS_3BET
    elif len(raise_before_hero) == 1:
        if hero_action.action == "raise":
            spot_type = SpotType.PREFLOP_3BET
        else:
            spot_type = SpotType.PREFLOP_VS_OPEN
    else:
        spot_type = SpotType.PREFLOP_OPEN

    return SpotInfo(
        hand_id=hand_id,
        spot_type=spot_type,
        street="preflop",
        hero_position=hero_position,
        hero_cards=hero_cards,
        hero_stack_bb=round(hero_stack_bb, 1),
        bb=bb,
        num_players_dealt=num_players_dealt,
        num_players_active=num_players_active,
        num_players_postflop=num_players_postflop,
        action_history=actions_before_hero,
        hero_action=hero_action,
        actions_after_hero=actions_after_hero,
    )


# ============================================================
# Пакетная классификация
# ============================================================

def classify_all(limit: int | None = None) -> list[SpotInfo]:
    """Классифицировать все раздачи. Возвращает список SpotInfo."""
    with transaction() as conn:
        rows = conn.execute("""
            SELECT h.id FROM hands h
            WHERE EXISTS (
                SELECT 1 FROM hand_players p
                WHERE p.hand_id = h.id AND p.is_hero = 1
            )
            ORDER BY h.played_at
        """).fetchall()
        if limit:
            rows = rows[:limit]

    out: list[SpotInfo] = []
    for row in rows:
        spot = classify_hand(row["id"])
        if spot is not None:
            out.append(spot)
    return out