"""Утилиты: парсинг карт, форматирование действий, компрессия."""

from __future__ import annotations

from pokerlab.desktop.constants import RANK_ORDER


def hand_label(i: int, j: int) -> str:
    r1, r2 = RANK_ORDER[i], RANK_ORDER[j]
    if i == j:
        return f"{r1}{r2}"
    if i < j:
        return f"{r1}{r2}s"
    return f"{r2}{r1}o"


def parse_cards(cards: str) -> list[tuple[str, str]]:
    if not cards or len(cards) != 4:
        return []
    return [(cards[0], cards[1]), (cards[2], cards[3])]


def compress_actions(actions: list[dict]) -> list[dict]:
    """Объединяет все post_ante в одно синтетическое действие."""
    result: list[dict] = []
    ante_sum = 0
    ante_count = 0
    ante_last: dict | None = None

    for a in actions:
        if a["action"] == "post_ante":
            ante_sum += a["amount"] or 0
            ante_count += 1
            ante_last = a
        else:
            if ante_last is not None:
                merged = dict(ante_last)
                merged["action"] = "post_ante_all"
                merged["amount"] = ante_sum
                merged["player_name"] = "Все игроки"
                merged["_ante_count"] = ante_count
                merged["pot_after"] = ante_last["pot_after"]
                result.append(merged)
                ante_last = None
                ante_sum = 0
                ante_count = 0
            result.append(a)

    if ante_last is not None:
        merged = dict(ante_last)
        merged["action"] = "post_ante_all"
        merged["amount"] = ante_sum
        merged["player_name"] = "Все игроки"
        merged["_ante_count"] = ante_count
        merged["pot_after"] = ante_last["pot_after"]
        result.append(merged)

    return result


def format_action(action: dict) -> str:
    a = action["action"]
    amt = action["amount"] or 0
    to = action["amount_to"] or 0
    allin = " ALL-IN" if action["is_all_in"] else ""

    if a == "post_ante_all":
        n = action.get("_ante_count", 0)
        return f"ANTE {amt:,} ({n} игроков)"
    if a == "post_ante":
        return f"ANTE {amt:,}"
    if a == "post_sb":
        return f"SB {amt:,}"
    if a == "post_bb":
        return f"BB {amt:,}"
    if a == "fold":
        return "FOLD"
    if a == "check":
        return "CHECK"
    if a == "call":
        return f"CALL {amt:,}{allin}"
    if a == "bet":
        return f"BET {amt:,}{allin}"
    if a == "raise":
        return f"RAISE {to:,}{allin}"
    return a.upper()