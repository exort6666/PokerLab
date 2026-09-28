"""
Классификация турниров по названию.
"""

from __future__ import annotations

import re


# Убираем префиксы вида "11-KO:", "134-NLH:", "14-NLH:"
_PREFIX_RE = re.compile(r"^\d+-(?:KO|NLH|NLHE|NL)\s*:\s*", re.IGNORECASE)


_TYPE_RULES: list[tuple[str, str]] = [
    # --- Sunday family (проверяем до Daily/общих) ---
    ("Sunday Marathon Bounty", "Sunday Marathon"),
    ("Sunday Marathon", "Sunday Marathon"),
    ("Sunday Mini Marathon", "Sunday Marathon"),
    ("Sunday Freezeout Bounty", "Sunday Freezeout"),
    ("Sunday Freezeout", "Sunday Freezeout"),
    ("Sunday Main Event", "Sunday Main Event"),
    ("Sunday Deep Stacks", "Sunday Deep Stacks"),
    ("Sunday Showdown", "Sunday Showdown"),
    ("Sunday Heater Bounty Turbo", "Sunday Heater"),
    ("Sunday Heater", "Sunday Heater"),
    ("Sunday Monster Stack", "Sunday Monster Stack"),
    ("Sunday Big", "Sunday Big"),
    ("Sunday Turbo", "Sunday Turbo"),
    ("Sunday Special", "Sunday Special"),
    
    # --- Сателлиты и Step-турниры (проверяем первыми) ---
    ("Satellite to", "Satellite"),
    ("Sat to", "Satellite"),
    ("WSOP Express", "Satellite"),
    ("Step 1 to", "Satellite"),
    ("Step 2 to", "Satellite"),
    ("Step 3 to", "Satellite"),
    ("Step 4 to", "Satellite"),
    ("[Day 1]", "Multi-Day"),
    ("[Day 2]", "Multi-Day"),
    ("[Final Day]", "Multi-Day"),

    # --- Специальные серии ---
    ("Mystery Bounty Main Event", "Mystery Bounty"),
    ("Mystery Bounty", "Mystery Bounty"),
    ("GGMasters Bounty", "GGMasters"),
    ("GGMasters", "GGMasters"),
    ("Global Festival", "Global Festival"),

    # --- Micro-серии ---
    ("Micro Madness", "Micro Madness"),
    ("Mini Hypersonic", "Hypersonic"),
    ("Hypersonic", "Hypersonic"),
    ("Mini Last Call", "Last Call"),
    ("Last Call", "Last Call"),
    ("Mini Superstack", "Superstack"),
    ("Superstack", "Superstack"),

    # --- Mini по дням недели ---
    ("Mini Monday Monster Stack", "Mini Monday"),
    ("Mini Tuesday Classic", "Mini Tuesday"),
    ("Mini Wednesday Double Stack", "Mini Wednesday"),
    ("Mini Thursday Throwdown", "Mini Thursday"),
    ("Mini Friday Night Fight", "Mini Friday"),
    ("Mini Saturday Knockout", "Mini Saturday"),
    ("Mini Sunday", "Mini Sunday"),

    # --- Saturday / Sunday Session ---
    ("Saturday Session", "Saturday Session"),
    ("Sunday Session", "Sunday Session"),

    # --- Big One (учитываем с префиксами [Big Bounties]) ---
    ("Big One", "Big One"),

    # --- Crazy Eights ---
    ("Crazy Eights", "Crazy Eights"),

    # --- Lucky Sevens ---
    ("Lucky Sevens", "Lucky Sevens"),

    # --- Super Six ---
    ("SUPER SIX", "Super Six"),
    ("Super Six", "Super Six"),

    # --- Bounty Hunters family ---
    ("Bounty Hunters Sunday Hyper Special", "Bounty Hunters Hyper"),
    ("Bounty Hunters Sunday", "Bounty Hunters Sunday"),
    ("Bounty Hunters Mini Main", "Bounty Hunters Mini Main"),
    ("Bounty Hunters Mini Big Game", "Bounty Hunters Mini Big Game"),
    ("Bounty Hunters Mini Encore", "Bounty Hunters Mini Encore"),
    ("Bounty Hunters Deepstack Turbo", "Bounty Hunters Deepstack"),
    ("Bounty Hunters Hyper Special", "Bounty Hunters Hyper"),
    ("Bounty Hunters Turbo Special", "Bounty Hunters Turbo"),
    ("Bounty Hunters Special", "Bounty Hunters Special"),
    ("Bounty Hunters Big One", "Bounty Hunters Big One"),
    ("Bounty Hunters Warm-up", "Bounty Hunters Warm-up"),
    ("Bounty Hunters Mini", "Bounty Hunters Mini"),
    ("Bounty Hunters", "Bounty Hunters"),

    # --- Bounty Warm-Up (отдельный от Bounty Hunters) ---
    ("Bounty Warm-Up", "Bounty Warm-Up"),

    # --- Bounty King ---
    ("Bounty King Jr", "Bounty King"),
    ("Bounty King", "Bounty King"),
    ("Sunday Bounty King", "Bounty King"),

    # --- Speed Racer ---
    ("Speed Racer Bounty", "Speed Racer Bounty"),

    # --- Daily family ---
    ("Daily Monster Stack", "Daily Monster Stack"),
    ("Daily Turbo", "Daily Turbo"),
    ("Daily Classic", "Daily Classic"),
    ("Daily Special", "Daily Special"),
    ("Daily Deepstack", "Daily Deepstack"),
    ("Daily Hyper", "Daily Hyper"),
    ("Daily", "Daily"),

    # --- Stack family ---
    ("Mini Forty Stack", "Mini Forty Stack"),
    ("Sunday Fifty Stack", "Fifty Stack"),
    ("Fifty Stack", "Fifty Stack"),
    ("Forty Stack", "Forty Stack"),

    # --- Heater ---
    ("Sunday Mini Heater", "Mini Heater"),
    ("Mini Heater", "Mini Heater"),

    # --- Zodiac ---
    ("Zodiac Opener", "Zodiac"),
    ("Zodiac Bounty", "Zodiac"),
    ("Zodiac Festival", "Zodiac"),
    ("Zodiac", "Zodiac"),

    # --- Прочее ---
    ("#ThanksGG", "Flipout"),
    ("Flipout", "Flipout"),
    ("T$ Builder", "T$ Builder"),
    ("Pick & Go", "Pick & Go"),
    ("Центролл", "Центролл"),
    ("Big Game", "Big Game"),
    ("Deepstack Turbo", "Deepstack Turbo"),
    ("Turbo Special", "Turbo Special"),
]


def classify_type(name: str) -> str:
    """Определить тип турнира по названию."""
    if not name:
        return "Other"

    # Убираем префиксы "134-NLH:", "11-KO:" и т.п.
    clean = _PREFIX_RE.sub("", name).strip()

    # Турниры без имени (summary-only, нет HH)
    if re.match(r"^Tournament #\d+$", clean):
        return "Без имени"

    for pattern, label in _TYPE_RULES:
        if pattern in clean:
            return label
    return "Other"


def classify_format(name: str) -> str:
    lower = name.lower()
    if "hyper" in lower:
        return "Hyper"
    if "turbo" in lower:
        return "Turbo"
    if "deepstack" in lower:
        return "Deepstack"
    return "Regular"


def classify_table_size(name: str) -> str:
    m = re.search(r"(\d+)-Max", name)
    if m:
        return f"{m.group(1)}-Max"
    return "9-Max"


DAY_NAMES_RU = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
]


def day_of_week_name(dow: int) -> str:
    return DAY_NAMES_RU[dow]