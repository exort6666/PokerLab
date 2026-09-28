from __future__ import annotations

import re
from datetime import datetime


# ------------------------------------------------------------
# Деньги и числа
# ------------------------------------------------------------

def parse_amount(s: str) -> int:
    """'1,400' -> 1400, '2,100' -> 2100, '0' -> 0."""
    return int(s.replace(",", "").strip())


# ------------------------------------------------------------
# Карты
# ------------------------------------------------------------

def parse_cards(s: str) -> str:
    """'8s 8c' -> '8s8c'. Пустая строка -> ''."""
    return s.replace(" ", "").strip()


# ------------------------------------------------------------
# Заголовок раздачи
# ------------------------------------------------------------

_HEADER_RE = re.compile(
    r"Poker Hand #(?P<hand_id>\w+): "
    r"Tournament #(?P<tour_id>\d+), "
    r"(?P<tour_name>.+?) "
    r"Hold'em No Limit - "
    r"Level(?P<level>\d+)\((?P<sb>[\d,]+)/(?P<bb>[\d,]+)\((?P<ante>[\d,]+)\)\) - "
    r"(?P<timestamp>.+)"
)


def parse_header(line: str) -> dict:
    """
    Разбирает строку вида:
    Poker Hand #TM6449350327: Tournament #313655961, Bounty Hunters Mini Main $5.40
    Hold'em No Limit - Level7(350/700(100)) - 2026/09/23 19:41:10
    """
    m = _HEADER_RE.match(line.strip())
    if not m:
        raise ValueError(f"Не удалось распарсить заголовок: {line!r}")
    d = m.groupdict()
    return {
        "hand_id": d["hand_id"],
        "tour_id": d["tour_id"],
        "tour_name": d["tour_name"].strip(),
        "level": int(d["level"]),
        "sb": parse_amount(d["sb"]),
        "bb": parse_amount(d["bb"]),
        "ante": parse_amount(d["ante"]),
        "timestamp": _to_iso(d["timestamp"].strip()),
    }


# ------------------------------------------------------------
# Стол
# ------------------------------------------------------------

_TABLE_RE = re.compile(
    r"Table '(?P<table>[^']+)' (?P<max>\d+)-max Seat #(?P<button>\d+) is the button"
)


def parse_table(line: str) -> dict:
    """
    'Table '240' 8-max Seat #5 is the button'
    -> {'table_name': '240', 'max_seats': 8, 'button_seat': 5}
    """
    m = _TABLE_RE.match(line.strip())
    if not m:
        raise ValueError(f"Не удалось распарсить стол: {line!r}")
    d = m.groupdict()
    return {
        "table_name": d["table"],
        "max_seats": int(d["max"]),
        "button_seat": int(d["button"]),
    }


# ------------------------------------------------------------
# Игроки
# ------------------------------------------------------------

_SEAT_RE = re.compile(
    r"Seat (?P<seat>\d+): (?P<name>\S+) \((?P<stack>[\d,]+) in chips\)"
)


def parse_seat(line: str) -> dict:
    """'Seat 1: b2d33314 (70,711 in chips)' -> {...}"""
    m = _SEAT_RE.match(line.strip())
    if not m:
        raise ValueError(f"Не удалось распарсить место: {line!r}")
    d = m.groupdict()
    return {
        "seat": int(d["seat"]),
        "name": d["name"],
        "stack_start": parse_amount(d["stack"]),
    }


# ------------------------------------------------------------
# Dealt to
# ------------------------------------------------------------

_DEALT_RE = re.compile(r"Dealt to (?P<name>\S+)(?: \[(?P<cards>[^\]]+)\])?")


def parse_dealt(line: str) -> tuple[str, str]:
    """
    'Dealt to Hero [8s 8c]' -> ('Hero', '8s8c')
    'Dealt to b2d33314 '    -> ('b2d33314', '')
    """
    m = _DEALT_RE.match(line.strip())
    if not m:
        raise ValueError(f"Не удалось распарсить Dealt to: {line!r}")
    cards = m.group("cards") or ""
    return m.group("name"), parse_cards(cards)


# ------------------------------------------------------------
# Время
# ------------------------------------------------------------

def _to_iso(ts: str) -> str:
    """'2026/09/23 19:41:10' -> '2026-09-23T19:41:10'."""
    try:
        dt = datetime.strptime(ts, "%Y/%m/%d %H:%M:%S")
        return dt.isoformat()
    except ValueError:
        return ts  # если формат другой — оставляем как есть
# ------------------------------------------------------------
# Позиции
# ------------------------------------------------------------

# Порядок в списке: по часовой стрелке, начиная с BTN.
# Длина списка = количеству игроков за столом.
_POSITION_SCHEMES: dict[int, list[str]] = {
    2: ["SB", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "HJ", "CO"],
    6: ["BTN", "SB", "BB", "MP", "HJ", "CO"],
    7: ["BTN", "SB", "BB", "UTG", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "MP", "MP1", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG1", "MP", "MP1", "HJ", "CO"],
}


def positions_for_size(n: int) -> list[str]:
    """Список позиций для стола с n игроками, по часовой от BTN."""
    if n not in _POSITION_SCHEMES:
        raise ValueError(f"Нет схемы позиций для {n} игроков")
    return _POSITION_SCHEMES[n]


def assign_positions(
    seats_in_order: list[int],
    button_seat: int,
) -> dict[int, str]:
    """
    Назначить позиции игрокам.

    seats_in_order: seat-номера игроков в раздаче, по возрастанию.
    button_seat:    seat-номер игрока на BTN.

    Возвращает {seat: position}.
    """
    if button_seat not in seats_in_order:
        raise ValueError(f"BTN seat {button_seat} не найден среди игроков")

    n = len(seats_in_order)
    positions = positions_for_size(n)

    btn_idx = seats_in_order.index(button_seat)
    result: dict[int, str] = {}
    for i, pos in enumerate(positions):
        seat = seats_in_order[(btn_idx + i) % n]
        result[seat] = pos
    return result