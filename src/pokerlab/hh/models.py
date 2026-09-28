from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Action:
    """Одно действие игрока за столом."""
    street: str                    # 'preflop', 'flop', 'turn', 'river'
    order: int                     # порядковый номер действия в раздаче
    seat: int
    player: str
    action: str                    # 'post_ante', 'post_sb', 'post_bb',
                                   # 'fold', 'check', 'call', 'bet', 'raise'
    amount: int = 0                # сколько добавлено в банк этим действием
    amount_to: int = 0             # итоговая ставка (для raise)
    is_all_in: bool = False
    pot_after: int = 0             # банк после действия


@dataclass
class PlayerInHand:
    """Игрок, участвующий в раздаче."""
    seat: int
    name: str
    stack_start: int
    cards: Optional[str] = None    # '8s8c' или None, если карты неизвестны
    position: Optional[str] = None # 'BTN', 'SB', 'BB', 'UTG', ...
    is_hero: bool = False


@dataclass
class Hand:
    """Одна раздача целиком."""
    id: str
    tournament_id: str
    tournament_name: str
    level: int
    sb: int
    bb: int
    ante: int
    table_name: str
    button_seat: int
    max_seats: int
    timestamp: str                 # ISO 8601
    players: list[PlayerInHand] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    board: str = ""
    total_pot: int = 0
    hero_seat: Optional[int] = None
    hero_cards: Optional[str] = None
    hero_position: Optional[str] = None
    hero_net: int = 0
    raw_text: str = ""


@dataclass
class Tournament:
    """Метаданные турнира."""
    id: str
    name: str
    buy_in_cents: Optional[int] = None
    is_bounty: bool = False
    start_date: Optional[str] = None