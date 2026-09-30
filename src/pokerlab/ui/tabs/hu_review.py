"""Вкладка «HU Review» — разбор HU push/fold спотов."""

from __future__ import annotations

import json
import sqlite3

import pandas as pd
import streamlit as st

from pokerlab.config import DB_PATH
from pokerlab.mtt.hu_solver import solve_hu_chipEV


RANK_ORDER = "AKQJT98765432"


# ============================================================
# HTML-рендер 13×13 таблицы диапазона
# ============================================================

def _hand_label(i: int, j: int) -> str:
    r1 = RANK_ORDER[i]
    r2 = RANK_ORDER[j]
    if i == j:
        return f"{r1}{r2}"
    if i < j:
        return f"{r1}{r2}s"
    return f"{r2}{r1}o"


def _range_html(hands: list[str], title: str, color: str) -> str:
    hand_set = set(hands)
    cell = "42px"
    border = "1px solid #333"
    html: list[str] = []
    html.append(
        f'<div style="margin: 10px 0;">'
        f'<div style="font-size: 14px; font-weight: bold; '
        f'margin-bottom: 8px;">{title}</div>'
        f'<table style="border-collapse: collapse; '
        f'font-family: Arial; text-align: center;">'
    )
    html.append('<tr>')
    html.append(
        f'<td style="width:{cell}; height:{cell}; border:{border}; '
        f'background:#fafafa;"></td>'
    )
    for r in RANK_ORDER:
        html.append(
            f'<td style="width:{cell}; height:{cell}; border:{border}; '
            f'background:#fafafa; font-weight:bold; font-size:13px;">{r}</td>'
        )
    html.append('</tr>')

    for i, r1 in enumerate(RANK_ORDER):
        html.append('<tr>')
        html.append(
            f'<td style="width:{cell}; height:{cell}; border:{border}; '
            f'background:#fafafa; font-weight:bold; font-size:13px;">{r1}</td>'
        )
        for j, r2 in enumerate(RANK_ORDER):
            label = _hand_label(i, j)
            in_range = label in hand_set
            if in_range:
                bg, fg, fw = color, "#ffffff", "bold"
            else:
                bg, fg, fw = "#f0f0f0", "#555", "normal"
            html.append(
                f'<td style="width:{cell}; height:{cell}; border:{border}; '
                f'background:{bg}; color:{fg}; font-weight:{fw}; '
                f'font-size:11px;">{label}</td>'
            )
        html.append('</tr>')
    html.append('</table></div>')
    return "".join(html)


# ============================================================
# Загрузка
# ============================================================

@st.cache_data
def _load_hu_spots() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT hand_id, spot_type, hero_action, optimal_action,
               is_correct, details
        FROM hand_analysis
        WHERE solver_name = 'hu_solver_chipEV'
    """, conn)
    conn.close()
    return df


def _load_hand_full(hand_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    hand = dict(conn.execute(
        "SELECT * FROM hands WHERE id = ?", (hand_id,)
    ).fetchone())
    players = [dict(r) for r in conn.execute(
        "SELECT * FROM hand_players WHERE hand_id = ? ORDER BY seat",
        (hand_id,),
    ).fetchall()]
    conn.close()
    return {"hand": hand, "players": players}


# ============================================================
# Рендер
# ============================================================

def render() -> None:
    st.markdown(
        '<div class="hands-title">HU Review</div>',
        unsafe_allow_html=True,
    )

    df = _load_hu_spots()
    if len(df) == 0:
        st.warning("Нет HU-спотов. Запусти run_hu_analysis.")
        return

    errors_only = st.checkbox("Только ошибки", value=True, key="hu_errors")
    df_show = df[df["is_correct"] == 0] if errors_only else df

    st.caption(f"Показано: {len(df_show)} из {len(df)}")

    display = df_show.copy()
    display["result"] = display.apply(
        lambda r: f"{r['hero_action']} → надо {r['optimal_action']}",
        axis=1,
    )
    display = display[[
        "hand_id", "spot_type", "hero_action", "optimal_action", "result",
    ]].rename(columns={
        "hand_id": "ID",
        "spot_type": "Тип",
        "hero_action": "Hero",
        "optimal_action": "Оптимально",
        "result": "Итог",
    })

    event = st.dataframe(
        display,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )

    if event.selection.rows:
        idx = event.selection.rows[0]
        hand_id = df_show.iloc[idx]["hand_id"]
        _render_spot(hand_id, df_show.iloc[idx].to_dict())


def _render_spot(hand_id: str, row: dict) -> None:
    details = json.loads(row["details"]) if row["details"] else {}
    data = _load_hand_full(hand_id)
    hand = data["hand"]
    players = data["players"]

    st.divider()
    st.subheader(f"Раздача {hand_id}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Тип спота", row["spot_type"].replace("PREFLOP_", ""))
    c2.metric("Hero сделал", row["hero_action"])
    c3.metric("Оптимально", row["optimal_action"])
    c4.metric("Карты Hero", details.get("hero_code", "?"))

    pusher_start = details.get("pusher_start_bb", 0)
    caller_start = details.get("caller_start_bb", 0)
    pusher_inv = details.get("pusher_inv_bb", 0)
    caller_inv = details.get("caller_inv_bb", 0)
    dead = details.get("dead_money_bb", 0)
    eff = min(pusher_start - pusher_inv, caller_start - caller_inv)

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Эффективный стек", f"{eff:.1f} BB")
    c6.metric("Pusher стек", f"{pusher_start:.1f} BB")
    c7.metric("Caller стек", f"{caller_start:.1f} BB")
    c8.metric("Dead money", f"{dead:.1f} BB")

    st.markdown("### Игроки за столом")
    pdf = pd.DataFrame(players)
    pdf["stack_bb"] = (pdf["stack_start"] / hand["bb"]).round(1)
    pdf = pdf[[
        "seat", "name", "position", "stack_start", "stack_bb",
        "cards", "is_hero",
    ]]
    pdf.columns = [
        "Seat", "Игрок", "Позиция", "Стек (чипы)",
        "Стек (BB)", "Карты", "Hero",
    ]
    st.dataframe(pdf, width="stretch", hide_index=True)

    # Пересчёт диапазона
    result = solve_hu_chipEV(
        pusher_start_bb=pusher_start,
        caller_start_bb=caller_start,
        pusher_inv_bb=pusher_inv,
        caller_inv_bb=caller_inv,
        dead_money_bb=dead,
        iterations=2000,
    )

    st.markdown("### Диапазоны (GTO)")

    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown(
            _range_html(
                result.push_range,
                f"Push range Pusher ({result.push_freq:.1f}%)",
                "#3498db",
            ),
            unsafe_allow_html=True,
        )
    with col_r:
        st.markdown(
            _range_html(
                result.call_range,
                f"Call range Caller ({result.call_freq:.1f}%)",
                "#e74c3c",
            ),
            unsafe_allow_html=True,
        )

    st.caption(
        f"Hero cards: **{details.get('hero_code', '?')}** | "
        f"в push_range: {details.get('hero_code') in result.push_range} | "
        f"в call_range: {details.get('hero_code') in result.call_range}"
    )