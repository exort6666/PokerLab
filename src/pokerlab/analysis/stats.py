from __future__ import annotations

from dataclasses import dataclass

from pokerlab.db.connection import transaction


@dataclass
class PositionStats:
    position: str
    hands: int
    net: int
    net_per_hand: float
    bb_per_100: float
    vpip: float
    pfr: float
    three_bet: float


def _bb_per_100(net: int, hands: int, avg_bb: float) -> float:
    """Net в bb/100. avg_bb — средний BB за эти раздачи."""
    if hands == 0 or avg_bb == 0:
        return 0.0
    return (net / avg_bb) / hands * 100


def stats_by_position() -> list[PositionStats]:
    """Отчёт по позициям Hero."""
    with transaction() as conn:
        # Основные счётчики: руки, net, средний BB
        rows = conn.execute("""
            SELECT
                hero_position AS position,
                COUNT(*) AS hands,
                COALESCE(SUM(hero_net), 0) AS net,
                COALESCE(AVG(bb), 0) AS avg_bb
            FROM hands
            WHERE hero_position IS NOT NULL
            GROUP BY hero_position
        """).fetchall()

        base = {r["position"]: dict(r) for r in rows}

        # VPIP: руки, где Hero сделал call/raise/bet префлоп
        # (исключая post_ante/post_sb/post_bb)
        vpip_rows = conn.execute("""
            SELECT h.hero_position AS position, COUNT(DISTINCT h.id) AS n
            FROM hands h
            JOIN actions a ON a.hand_id = h.id
            WHERE a.player_name = 'Hero'
              AND a.street = 'preflop'
              AND a.action IN ('call', 'bet', 'raise')
              AND h.hero_position IS NOT NULL
            GROUP BY h.hero_position
        """).fetchall()
        vpip = {r["position"]: r["n"] for r in vpip_rows}

        # PFR: руки, где Hero сделал raise префлоп
        pfr_rows = conn.execute("""
            SELECT h.hero_position AS position, COUNT(DISTINCT h.id) AS n
            FROM hands h
            JOIN actions a ON a.hand_id = h.id
            WHERE a.player_name = 'Hero'
              AND a.street = 'preflop'
              AND a.action = 'raise'
              AND h.hero_position IS NOT NULL
            GROUP BY h.hero_position
        """).fetchall()
        pfr = {r["position"]: r["n"] for r in pfr_rows}

        # 3-bet: руки, где Hero сделал raise префлоп ПОСЛЕ чужого raise
        threebet_rows = conn.execute("""
            SELECT h.hero_position AS position, COUNT(DISTINCT h.id) AS n
            FROM hands h
            JOIN actions a ON a.hand_id = h.id
            WHERE a.player_name = 'Hero'
              AND a.street = 'preflop'
              AND a.action = 'raise'
              AND EXISTS (
                  SELECT 1 FROM actions a2
                  WHERE a2.hand_id = h.id
                    AND a2.street = 'preflop'
                    AND a2.action = 'raise'
                    AND a2.action_order < a.action_order
                    AND a2.player_name != 'Hero'
              )
              AND h.hero_position IS NOT NULL
            GROUP BY h.hero_position
        """).fetchall()
        threebet = {r["position"]: r["n"] for r in threebet_rows}

    result: list[PositionStats] = []
    for pos, d in base.items():
        hands = d["hands"]
        net = d["net"]
        avg_bb = d["avg_bb"]
        v = vpip.get(pos, 0)
        p = pfr.get(pos, 0)
        t = threebet.get(pos, 0)
        result.append(PositionStats(
            position=pos,
            hands=hands,
            net=net,
            net_per_hand=net / hands if hands else 0.0,
            bb_per_100=_bb_per_100(net, hands, avg_bb),
            vpip=v / hands * 100 if hands else 0.0,
            pfr=p / hands * 100 if hands else 0.0,
            three_bet=t / hands * 100 if hands else 0.0,
        ))

    # Сортируем по позиции в стандартном порядке
    order = ["UTG", "UTG1", "UTG2", "MP", "MP1", "HJ", "CO", "BTN", "SB", "BB"]
    result.sort(key=lambda x: order.index(x.position) if x.position in order else 99)
    return result
@dataclass
class StackStats:
    bucket: str
    hands: int
    net: int
    net_per_hand: float
    bb_per_100: float


_STACK_BUCKETS = [
    ("0-10", 0, 10),
    ("10-15", 10, 15),
    ("15-20", 15, 20),
    ("20-30", 20, 30),
    ("30-50", 30, 50),
    ("50-75", 50, 75),
    ("75-100", 75, 100),
    ("100+", 100, 10**9),
]


def stats_by_stack() -> list[StackStats]:
    """Отчёт по стекам Hero (в BB)."""
    with transaction() as conn:
        rows = conn.execute("""
            SELECT
                h.id,
                h.hero_net,
                h.bb,
                p.stack_start
            FROM hands h
            JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
            WHERE h.bb > 0
        """).fetchall()

    buckets: dict[str, dict] = {b[0]: {"hands": 0, "net": 0, "bb_sum": 0}
                                for b in _STACK_BUCKETS}

    for r in rows:
        stack_bb = r["stack_start"] / r["bb"]
        net = r["hero_net"] or 0
        bb = r["bb"]
        for name, lo, hi in _STACK_BUCKETS:
            if lo <= stack_bb < hi:
                buckets[name]["hands"] += 1
                buckets[name]["net"] += net
                buckets[name]["bb_sum"] += bb
                break

    result: list[StackStats] = []
    for name, _, _ in _STACK_BUCKETS:
        b = buckets[name]
        hands = b["hands"]
        net = b["net"]
        avg_bb = b["bb_sum"] / hands if hands else 0
        result.append(StackStats(
            bucket=name,
            hands=hands,
            net=net,
            net_per_hand=net / hands if hands else 0.0,
            bb_per_100=_bb_per_100(net, hands, avg_bb),
        ))
    return result
# ============================================================
# Классификация турниров
# ============================================================

@dataclass
class BucketStats:
    key: str
    tournaments: int
    cost: float           # $
    payout: float         # $
    profit: float         # $
    roi_pct: float
    itm_count: int
    itm_pct: float


def _load_results_df() -> "pd.DataFrame":
    """Загрузить результаты в pandas для удобства группировок."""
    import pandas as pd
    from pokerlab.db.connection import get_connection

    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT
            r.tournament_id,
            t.name AS tournament_name,
            r.buyin_cents,
            r.rake_cents,
            r.bounty_cents,
            r.field_size,
            r.hero_place,
            r.hero_payout_cents,
            r.itm,
            r.started_at,
            r.currency
        FROM tournament_results r
        JOIN tournaments t ON t.id = r.tournament_id
        """,
        conn,
    )
    conn.close()

    df["buyin_total"] = (
        df["buyin_cents"] + df["rake_cents"] + df["bounty_cents"]
    ) / 100
    df["payout"] = df["hero_payout_cents"] / 100
    df["profit"] = df["payout"] - df["buyin_total"]
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    return df


def _bucket_stats(df, key_col: str, key_val: str) -> BucketStats:
    """Сводка по одной группе."""
    if len(df) == 0:
        return BucketStats(
            key=key_val, tournaments=0, cost=0.0, payout=0.0,
            profit=0.0, roi_pct=0.0, itm_count=0, itm_pct=0.0,
        )
    cost = float(df["buyin_total"].sum())
    payout = float(df["payout"].sum())
    profit = payout - cost
    roi = profit / cost * 100 if cost > 0 else 0.0
    itm_count = int(df["itm"].sum())
    itm_pct = itm_count / len(df) * 100
    return BucketStats(
        key=key_val,
        tournaments=len(df),
        cost=cost,
        payout=payout,
        profit=profit,
        roi_pct=roi,
        itm_count=itm_count,
        itm_pct=itm_pct,
    )


def stats_by_type() -> list[BucketStats]:
    """ROI по типам турниров (Bounty Hunters, Daily Turbo, Zodiac, ...)."""
    from pokerlab.analysis.classify import classify_type

    df = _load_results_df()
    df = df[df["currency"] != "SAT"].copy()  # исключаем сателлиты
    df["type"] = df["tournament_name"].apply(classify_type)

    out: list[BucketStats] = []
    for t in sorted(df["type"].unique()):
        sub = df[df["type"] == t]
        out.append(_bucket_stats(sub, "type", t))
    out.sort(key=lambda x: x.profit)
    return out


def stats_by_format() -> list[BucketStats]:
    """ROI по форматам (Turbo, Hyper, Deepstack, Regular)."""
    from pokerlab.analysis.classify import classify_format

    df = _load_results_df()
    df = df[df["currency"] != "SAT"].copy()
    df["format"] = df["tournament_name"].apply(classify_format)

    out: list[BucketStats] = []
    for t in sorted(df["format"].unique()):
        sub = df[df["format"] == t]
        out.append(_bucket_stats(sub, "format", t))
    out.sort(key=lambda x: x.profit)
    return out


def stats_by_day_of_week() -> list[BucketStats]:
    """ROI по дням недели."""
    from pokerlab.analysis.classify import day_of_week_name

    df = _load_results_df()
    df = df[df["currency"] != "SAT"].dropna(subset=["started_at"]).copy()
    df["dow"] = df["started_at"].dt.dayofweek  # 0=Monday

    out: list[BucketStats] = []
    for d in sorted(df["dow"].unique()):
        sub = df[df["dow"] == d]
        out.append(_bucket_stats(sub, "dow", day_of_week_name(int(d))))
    return out


def stats_by_hour() -> list[BucketStats]:
    """ROI по часам суток."""
    df = _load_results_df()
    df = df[df["currency"] != "SAT"].dropna(subset=["started_at"]).copy()
    df["hour"] = df["started_at"].dt.hour

    out: list[BucketStats] = []
    for h in sorted(df["hour"].unique()):
        sub = df[df["hour"] == h]
        out.append(_bucket_stats(sub, "hour", f"{int(h):02d}:00"))
    return out