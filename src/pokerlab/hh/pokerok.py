from __future__ import annotations

import logging
import re
from pathlib import Path

from pokerlab.hh.models import Action, Hand, PlayerInHand
from pokerlab.hh.utils import (
    assign_positions,
    parse_amount,
    parse_cards,
    parse_dealt,
    parse_header,
    parse_seat,
    parse_table,
)

log = logging.getLogger(__name__)


# ------------------------------------------------------------
# Разбивка файла на блоки раздач
# ------------------------------------------------------------

_HAND_START_RE = re.compile(r"^Poker Hand #\w+")


def split_hands(text: str) -> list[str]:
    """Разбить текст файла на блоки раздач."""
    blocks: list[list[str]] = []
    current: list[str] = []

    for line in text.splitlines():
        if _HAND_START_RE.match(line):
            if current:
                blocks.append(current)
            current = [line]
        else:
            if current:
                current.append(line)

    if current:
        blocks.append(current)

    return ["\n".join(b).strip() for b in blocks if b]


# ------------------------------------------------------------
# Регулярки
# ------------------------------------------------------------

_ANTE_RE = re.compile(r"^(?P<name>\S+): posts the ante (?P<amount>[\d,]+)$")
_SB_RE = re.compile(r"^(?P<name>\S+): posts small blind (?P<amount>[\d,]+)$")
_BB_RE = re.compile(r"^(?P<name>\S+): posts big blind (?P<amount>[\d,]+)$")

_FOLD_RE = re.compile(r"^(?P<name>\S+): folds$")
_CHECK_RE = re.compile(r"^(?P<name>\S+): checks$")
_CALL_RE = re.compile(r"^(?P<name>\S+): calls (?P<amount>[\d,]+)(?: and is all-in)?$")
_BET_RE = re.compile(r"^(?P<name>\S+): bets (?P<amount>[\d,]+)(?: and is all-in)?$")
_RAISE_RE = re.compile(
    r"^(?P<name>\S+): raises (?P<raise_by>[\d,]+) to (?P<to>[\d,]+)"
    r"(?: and is all-in)?$"
)

_UNCALLED_RE = re.compile(
    r"^Uncalled bet \((?P<amount>[\d,]+)\) returned to (?P<name>\S+)$"
)
_SHOWS_RE = re.compile(r"^(?P<name>\S+): shows \[(?P<cards>[^\]]+)\]")

_COLLECTED_BODY_RE = re.compile(
    r"^(?P<name>\S+):? collected (?P<amount>[\d,]+) from pot$"
)

_FLOP_RE = re.compile(r"^\*\*\* FLOP \*\*\* \[(?P<cards>[^\]]+)\]")
_TURN_RE = re.compile(r"^\*\*\* TURN \*\*\* \[[^\]]+\] \[(?P<card>[^\]]+)\]")
_RIVER_RE = re.compile(r"^\*\*\* RIVER \*\*\* \[[^\]]+\] \[(?P<card>[^\]]+)\]")

_TOTAL_POT_RE = re.compile(r"^Total pot (?P<pot>[\d,]+)")


# ------------------------------------------------------------
# Парсинг одной раздачи
# ------------------------------------------------------------

def parse_hand(text: str) -> Hand:
    """Распарсить одну раздачу. Возвращает Hand."""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        raise ValueError("Пустой блок раздачи")

    header = parse_header(lines[0])

    hand = Hand(
        id=header["hand_id"],
        tournament_id=header["tour_id"],
        tournament_name=header["tour_name"],
        level=header["level"],
        sb=header["sb"],
        bb=header["bb"],
        ante=header["ante"],
        table_name="",
        button_seat=0,
        max_seats=9,
        timestamp=header["timestamp"],
        raw_text=text,
    )

    street = "preflop"
    action_order = 0
    pot = 0
    hero_name = "Hero"

    dealt_cards: dict[str, str] = {}
    shown_cards: dict[str, str] = {}
    hero_committed = 0
    hero_collected = 0
    in_summary = False

    # Стейт улицы: сколько каждый игрок вложил на текущей улице.
    committed_street: dict[str, int] = {}
    # Текущая максимальная ставка на улице (для call/raise).
    current_bet = 0

    for line in lines[1:]:
        # --- Table ---
        if line.startswith("Table '"):
            t = parse_table(line)
            hand.table_name = t["table_name"]
            hand.max_seats = t["max_seats"]
            hand.button_seat = t["button_seat"]
            continue

        # --- Seat ---
        if line.startswith("Seat "):
            try:
                s = parse_seat(line)
            except ValueError:
                continue
            hand.players.append(PlayerInHand(
                seat=s["seat"],
                name=s["name"],
                stack_start=s["stack_start"],
                is_hero=(s["name"] == hero_name),
            ))
            if s["name"] == hero_name:
                hand.hero_seat = s["seat"]
            continue

        # --- Dealt to ---
        if line.startswith("Dealt to "):
            try:
                name, cards = parse_dealt(line)
            except ValueError:
                continue
            if cards:
                dealt_cards[name] = cards
            continue

        # --- Улицы ---
        if line.startswith("*** HOLE CARDS ***"):
            street = "preflop"
            continue
        if line.startswith("*** FLOP ***"):
            street = "flop"
            committed_street = {}
            current_bet = 0
            m = _FLOP_RE.match(line)
            if m:
                hand.board = parse_cards(m.group("cards"))
            continue
        if line.startswith("*** TURN ***"):
            street = "turn"
            committed_street = {}
            current_bet = 0
            m = _TURN_RE.match(line)
            if m:
                hand.board += parse_cards(m.group("card"))
            continue
        if line.startswith("*** RIVER ***"):
            street = "river"
            committed_street = {}
            current_bet = 0
            m = _RIVER_RE.match(line)
            if m:
                hand.board += parse_cards(m.group("card"))
            continue
        if line.startswith("*** SHOWDOWN ***"):
            street = "showdown"
            continue
        if line.startswith("*** SUMMARY ***"):
            street = "summary"
            in_summary = True
            continue

        # --- Всё, что ниже — только до SUMMARY ---
        if in_summary:
            m = _TOTAL_POT_RE.match(line)
            if m:
                hand.total_pot = parse_amount(m.group("pot"))
            continue

        # --- Действия ---
        result = _parse_action_line(
            line, street, action_order, hand,
            pot, committed_street, current_bet,
        )
        if result is not None:
            action, committed_street, current_bet = result
            action_order += 1
            action.order = action_order
            hand.actions.append(action)
            pot = action.pot_after
            if action.player == hero_name:
                hero_committed += action.amount
            continue

        # --- Uncalled bet ---
        m = _UNCALLED_RE.match(line)
        if m:
            amount = parse_amount(m.group("amount"))
            name = m.group("name")
            pot -= amount
            if name == hero_name:
                hero_committed -= amount
            continue

        # --- Shows ---
        m = _SHOWS_RE.match(line)
        if m:
            name = m.group("name")
            shown_cards[name] = parse_cards(m.group("cards"))
            continue

        # --- Collected (только в теле, до SUMMARY) ---
        m = _COLLECTED_BODY_RE.match(line)
        if m:
            name = m.group("name") or m.group("name2")
            amt_str = m.group("amount") or m.group("amount2")
            amount = parse_amount(amt_str)
            if name == hero_name:
                hero_collected += amount
            continue

    # --- Финализация ---
    hand.players = [p for p in hand.players if p.seat != 0]

    for p in hand.players:
        if p.name in dealt_cards:
            p.cards = dealt_cards[p.name]
        elif p.name in shown_cards:
            p.cards = shown_cards[p.name]

    for p in hand.players:
        if p.is_hero:
            hand.hero_cards = p.cards
            break

    # --- Позиции ---
    if hand.players:
        seats_in_order = sorted(p.seat for p in hand.players)
        try:
            pos_map = assign_positions(seats_in_order, hand.button_seat)
            for p in hand.players:
                p.position = pos_map.get(p.seat)
            for p in hand.players:
                if p.is_hero:
                    hand.hero_position = p.position
                    break
        except ValueError as e:
            log.warning("Не удалось назначить позиции для %s: %s", hand.id, e)

    # Ограничение: Hero не мог вложить больше своего стека
    hero_stack = next((p.stack_start for p in hand.players if p.is_hero), None)
    if hero_stack is not None and hero_committed > hero_stack:
        hero_committed = hero_stack

    if hero_committed or hero_collected:
        hand.hero_net = hero_collected - hero_committed

    return hand


# ------------------------------------------------------------
# Парсинг одной строки-действия
# ------------------------------------------------------------

def _parse_action_line(
    line: str,
    street: str,
    order: int,
    hand: Hand,
    pot: int,
    committed_street: dict[str, int],
    current_bet: int,
) -> tuple[Action, dict[str, int], int] | None:
    """
    Вернуть (Action, обновлённый committed_street, обновлённый current_bet).
    Или None, если строка не действие.
    """
    seat_by_name = {p.name: p.seat for p in hand.players}

    def make(
        name: str,
        act: str,
        amount: int,
        amount_to: int = 0,
        is_all_in: bool = False,
    ) -> tuple[Action, dict[str, int], int] | None:
        seat = seat_by_name.get(name)
        if seat is None:
            return None

        new_committed = dict(committed_street)
        new_current_bet = current_bet

        if act not in ("post_ante", "fold", "check"):
            new_committed[name] = new_committed.get(name, 0) + amount

        if act == "post_sb":
            new_current_bet = new_committed[name]
        elif act == "post_bb":
            new_current_bet = new_committed[name]
        elif act == "bet":
            new_current_bet = new_committed[name]
        elif act == "raise":
            new_current_bet = new_committed[name]
        elif act == "call":
            new_current_bet = max(current_bet, new_committed[name])

        action = Action(
            street=street,
            order=order,
            seat=seat,
            player=name,
            action=act,
            amount=amount,
            amount_to=amount_to,
            is_all_in=is_all_in,
            pot_after=pot + amount,
        )
        return action, new_committed, new_current_bet

    def remaining_stack(name: str) -> int:
        player = next((p for p in hand.players if p.name == name), None)
        if player is None:
            return 0
        already_this_hand = sum(a.amount for a in hand.actions if a.player == name)
        return max(0, player.stack_start - already_this_hand)

    m = _ANTE_RE.match(line)
    if m:
        return make(m.group("name"), "post_ante", parse_amount(m.group("amount")))

    m = _SB_RE.match(line)
    if m:
        return make(m.group("name"), "post_sb", parse_amount(m.group("amount")))

    m = _BB_RE.match(line)
    if m:
        return make(m.group("name"), "post_bb", parse_amount(m.group("amount")))

    m = _FOLD_RE.match(line)
    if m:
        return make(m.group("name"), "fold", 0)

    m = _CHECK_RE.match(line)
    if m:
        return make(m.group("name"), "check", 0)

    m = _CALL_RE.match(line)
    if m:
        name = m.group("name")
        raw_amount = parse_amount(m.group("amount"))
        already = committed_street.get(name, 0)
        if "all-in" in line:
            amount = min(raw_amount, remaining_stack(name))
            to = already + amount
        else:
            to = current_bet
            amount = max(0, to - already)
            amount = min(amount, remaining_stack(name))
        return make(name, "call", amount, to, is_all_in="all-in" in line)

    m = _BET_RE.match(line)
    if m:
        name = m.group("name")
        raw = parse_amount(m.group("amount"))
        amount = min(raw, remaining_stack(name))
        return make(name, "bet", amount, amount, is_all_in="all-in" in line)

    m = _RAISE_RE.match(line)
    if m:
        name = m.group("name")
        to = parse_amount(m.group("to"))
        already = committed_street.get(name, 0)
        amount = max(0, to - already)
        amount = min(amount, remaining_stack(name))
        return make(name, "raise", amount, already + amount,
                    is_all_in="all-in" in line)

    return None


# ------------------------------------------------------------
# Парсинг файла целиком
# ------------------------------------------------------------

def parse_file(path: str | Path) -> list[Hand]:
    """Прочитать файл и распарсить все раздачи."""
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    blocks = split_hands(text)
    hands: list[Hand] = []
    for i, block in enumerate(blocks, 1):
        try:
            hands.append(parse_hand(block))
        except Exception as e:
            log.error("Ошибка в раздаче #%d (%s): %s", i, path.name, e)
    return hands