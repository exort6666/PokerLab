from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class Suit(IntEnum):
    CLUBS = 0
    DIAMONDS = 1
    HEARTS = 2
    SPADES = 3


SUIT_CHARS = "cdhs"
RANK_CHARS = "23456789TJQKA"


@dataclass(frozen=True, slots=True)
class Card:
    rank: int   # 2..14 (14 = Ace)
    suit: Suit

    @staticmethod
    def parse(s: str) -> "Card":
        if len(s) != 2:
            raise ValueError(f"bad card: {s!r}")
        r, su = s[0].upper(), s[1].lower()
        if r not in RANK_CHARS or su not in SUIT_CHARS:
            raise ValueError(f"bad card: {s!r}")
        return Card(RANK_CHARS.index(r) + 2, Suit(SUIT_CHARS.index(su)))

    def __str__(self) -> str:
        return RANK_CHARS[self.rank - 2] + SUIT_CHARS[int(self.suit)]


def parse_cards(s: str) -> list[Card]:
    """'AhKsQd' или 'Ah Ks Qd' -> [Card, Card, Card]."""
    s = s.replace(" ", "")
    if len(s) % 2 != 0:
        raise ValueError(f"odd number of chars: {s!r}")
    return [Card.parse(s[i:i + 2]) for i in range(0, len(s), 2)]


# Все 52 карты
ALL_CARDS: tuple[Card, ...] = tuple(
    Card(rank, Suit(suit))
    for rank in range(2, 15)
    for suit in range(4)
)