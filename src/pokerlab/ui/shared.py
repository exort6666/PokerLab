"""Общие функции, стили и загрузчики для всех вкладок."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from pokerlab.config import DB_PATH


# ============================================================
# Стили Plotly
# ============================================================

GREEN = "#2ecc71"
RED = "#e74c3c"
GREY = "#95a5a6"

COLOR_CONTINUOUS = [
    [0.0, "#c0392b"],
    [0.35, "#e74c3c"],
    [0.5, "#f39c12"],
    [0.65, "#2ecc71"],
    [1.0, "#27ae60"],
]


def style_bar(fig, height: int = 420) -> None:
    fig.update_traces(
        marker_line_color="black",
        marker_line_width=1.5,
        textfont=dict(size=14, color="#111"),
    )
    fig.update_layout(
        height=height,
        showlegend=False,
        font=dict(size=15, color="#111"),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=False, linecolor="#333",
                   linewidth=1.5, tickfont=dict(size=13)),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0",
                   linecolor="#333", linewidth=1.5,
                   tickfont=dict(size=14)),
    )


def style_line(fig, height: int = 460) -> None:
    fig.update_traces(
        line=dict(width=3),
        marker=dict(size=8, line=dict(width=1.5, color="black")),
    )
    fig.update_layout(
        height=height,
        showlegend=False,
        font=dict(size=15, color="#111"),
        plot_bgcolor="#fafafa",
        paper_bgcolor="#ffffff",
        xaxis=dict(showgrid=True, gridcolor="#e0e0e0",
                   linecolor="#333", linewidth=1.5,
                   tickfont=dict(size=14)),
        yaxis=dict(showgrid=True, gridcolor="#e0e0e0",
                   linecolor="#333", linewidth=1.5,
                   tickfont=dict(size=14)),
    )


# ============================================================
# Загрузчики данных
# ============================================================

@st.cache_data
def load_hands() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            h.id, h.tournament_id, t.name AS tournament_name,
            h.level, h.sb, h.bb, h.ante,
            h.played_at, h.hero_position, h.hero_cards,
            h.hero_net, h.total_pot, h.board,
            h.button_seat, h.max_seats,
            p.stack_start AS hero_stack
        FROM hands h
        JOIN tournaments t ON t.id = h.tournament_id
        LEFT JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
        ORDER BY h.played_at
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["stack_bb"] = df["hero_stack"] / df["bb"]
    df["net_bb"] = df["hero_net"] / df["bb"]
    df["played_at"] = pd.to_datetime(df["played_at"])
    return df


@st.cache_data
def load_hand_detail(hand_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    hand = dict(conn.execute(
        "SELECT * FROM hands WHERE id = ?", (hand_id,)
    ).fetchone())
    players = [dict(r) for r in conn.execute(
        "SELECT * FROM hand_players WHERE hand_id = ? ORDER BY seat",
        (hand_id,),
    ).fetchall()]
    actions = [dict(r) for r in conn.execute(
        "SELECT * FROM actions WHERE hand_id = ? ORDER BY action_order",
        (hand_id,),
    ).fetchall()]
    conn.close()
    return {"hand": hand, "players": players, "actions": actions}


@st.cache_data
def load_results() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            r.tournament_id, t.name AS tournament_name,
            r.buyin_cents, r.rake_cents, r.bounty_cents,
            r.field_size, r.prize_pool_cents,
            r.hero_place, r.hero_payout_cents,
            r.itm, r.started_at, r.currency
        FROM tournament_results r
        JOIN tournaments t ON t.id = r.tournament_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["buyin_total"] = (
        df["buyin_cents"] + df["rake_cents"] + df["bounty_cents"]
    ) / 100
    df["payout"] = df["hero_payout_cents"] / 100
    df["cost"] = df["buyin_total"]
    df["profit"] = df["payout"] - df["cost"]
    df["roi_pct"] = (
        df["profit"] / df["cost"] * 100
    ).where(df["cost"] > 0, 0)
    df["place_pct"] = (
        df["hero_place"] / df["field_size"] * 100
    ).where(df["field_size"] > 0)
    df["started_at"] = pd.to_datetime(df["started_at"], errors="coerce")
    return df


# ============================================================
# Хелперы
# ============================================================

def bb_per_100(group: pd.DataFrame) -> float:
    if len(group) == 0:
        return 0.0
    avg_bb = group["bb"].mean()
    if avg_bb == 0:
        return 0.0
    return group["hero_net"].sum() / avg_bb / len(group) * 100


def color_row(row) -> list[str]:
    if row["Профит ($)"] > 0:
        return ["background-color: #d4edda"] * len(row)
    if row["Профит ($)"] == 0:
        return ["background-color: #eeeeee"] * len(row)
    return ["background-color: #f8d7da"] * len(row)


def filter_by_period(df_in: pd.DataFrame, period: str) -> pd.DataFrame:
    """Фильтр по последнему периоду от максимальной даты."""
    if period == "Всё время" or len(df_in) == 0:
        return df_in
    sub = df_in.dropna(subset=["started_at"])
    if len(sub) == 0:
        return df_in
    ref = sub["started_at"].max()
    days = {"День": 1, "Неделя": 7, "Месяц": 30, "Год": 365}.get(period)
    if days is None:
        return df_in
    cutoff = ref - pd.Timedelta(days=days)
    return df_in[df_in["started_at"] >= cutoff]