from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class TournamentResult:
    tournament_id: int
    name: str = ""                    # <-- НОВОЕ
    buyin_cents: int = 0
    rake_cents: int = 0
    bounty_cents: int = 0
    field_size: int = 0
    prize_pool_cents: int = 0
    hero_place: int | None = None
    hero_payout_cents: int = 0
    itm: bool = False
    started_at: str | None = None
    currency: str = "USD"


_HEADER_RE = re.compile(
    r"^Tournament #(?P<id>\d+), (?P<name>.+?), (?P<game>.+)$"
)
_BUYIN_RE = re.compile(r"^Buy-in:\s*(?P<rest>.+)$")
_MONEY_RE = re.compile(r"[$¥€]\s*([\d.]+)")
_FIELD_RE = re.compile(r"^(?P<field>[\d,]+) Players$")
_PRIZE_RE = re.compile(r"^Total Prize Pool: [\$¥€](?P<prize>[\d,]+\.?\d*)$")
_STARTED_RE = re.compile(r"^Tournament started (?P<date>.+)$")
_PLACE_RE = re.compile(
    r"^(?P<place>\d+)(?:st|nd|rd|th) : Hero, [\$¥€](?P<payout>[\d.]+)$"
)
_FINISH_RE = re.compile(
    r"^You finished the tournament in (?P<place>\d+)(?:st|nd|rd|th) place\.$"
)
_RECEIVED_RE = re.compile(
    r"^You received a total of [\$¥€](?P<payout>[\d.]+)\.$"
)


def _to_cents(s: str) -> int:
    return int(round(float(s.replace(",", "")) * 100))


def parse_summary(text: str) -> TournamentResult | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None

    m = _HEADER_RE.match(lines[0])
    if not m:
        return None

    raw_name = m.group("name").strip()
    result = TournamentResult(
        tournament_id=int(m.group("id")),
        name=raw_name,
    )

    # Определяем валюту
    if "¥" in raw_name or "Zodiac" in raw_name:
        result.currency = "CNY"
    elif "€" in raw_name:
        result.currency = "EUR"
    else:
        result.currency = "USD"

    for line in lines[1:]:
        m = _BUYIN_RE.match(line)
        if m:
            amounts = _MONEY_RE.findall(m.group("rest"))
            if len(amounts) >= 1:
                result.buyin_cents = _to_cents(amounts[0])
            if len(amounts) >= 2:
                result.rake_cents = _to_cents(amounts[1])
            if len(amounts) >= 3:
                result.bounty_cents = _to_cents(amounts[2])
            continue

        m = _FIELD_RE.match(line)
        if m:
            result.field_size = int(m.group("field").replace(",", ""))
            continue

        m = _PRIZE_RE.match(line)
        if m:
            result.prize_pool_cents = _to_cents(m.group("prize"))
            continue

        m = _STARTED_RE.match(line)
        if m:
            result.started_at = m.group("date").strip()
            continue

        m = _PLACE_RE.match(line)
        if m:
            result.hero_place = int(m.group("place"))
            result.hero_payout_cents = _to_cents(m.group("payout"))
            result.itm = (
                result.hero_payout_cents > 0
                and result.field_size > 0
                and result.hero_place <= result.field_size * 0.15
            )
            continue

        m = _FINISH_RE.match(line)
        if m and result.hero_place is None:
            result.hero_place = int(m.group("place"))
            continue

        m = _RECEIVED_RE.match(line)
        if m:
            result.hero_payout_cents = _to_cents(m.group("payout"))
            result.itm = (
                result.hero_payout_cents > 0
                and result.field_size > 0
                and result.hero_place is not None
                and result.hero_place <= result.field_size * 0.15
            )
            continue

    return result


def parse_summary_file(path: str | Path) -> TournamentResult | None:
    path = Path(path)
    text = path.read_text(encoding="utf-8", errors="replace")
    return parse_summary(text)