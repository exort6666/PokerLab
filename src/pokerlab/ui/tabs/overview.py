"""Вкладка «Обзор» — профиль игрока."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from pokerlab.config import DB_PATH
from pokerlab.ui.shared import bb_per_100


@st.cache_data
def _compute_preflop_stats() -> dict:
    """VPIP / PFR / 3bet по всем раздачам. Один раз, кэшируется."""
    conn = sqlite3.connect(DB_PATH)
    hands = conn.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    if hands == 0:
        conn.close()
        return {"vpip": 0.0, "pfr": 0.0, "threebet": 0.0}

    vpip = conn.execute("""
        SELECT COUNT(DISTINCT h.id) FROM hands h
        JOIN actions a ON a.hand_id = h.id
        WHERE a.player_name = 'Hero'
          AND a.street = 'preflop'
          AND a.action IN ('call', 'bet', 'raise')
    """).fetchone()[0]

    pfr = conn.execute("""
        SELECT COUNT(DISTINCT h.id) FROM hands h
        JOIN actions a ON a.hand_id = h.id
        WHERE a.player_name = 'Hero'
          AND a.street = 'preflop'
          AND a.action = 'raise'
    """).fetchone()[0]

    threebet = conn.execute("""
        SELECT COUNT(DISTINCT h.id) FROM hands h
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
    """).fetchone()[0]

    conn.close()
    return {
        "vpip": vpip / hands * 100,
        "pfr": pfr / hands * 100,
        "threebet": threebet / hands * 100,
    }


def _card(
    label: str,
    value: str,
    subtitle: str = "",
    color: str = "#0f172a",
) -> str:
    """Одна карточка метрики."""
    sub = (
        f'<div style="font-size: 12px; color: #94a3b8; '
        f'margin-top: 6px;">{subtitle}</div>'
        if subtitle else ""
    )
    return f"""
    <div style="
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 20px 22px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        height: 100%;
    ">
        <div style="
            font-size: 11px;
            color: #64748b;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.6px;
            margin-bottom: 10px;
        ">{label}</div>
        <div style="
            font-size: 30px;
            font-weight: 700;
            color: {color};
            letter-spacing: -0.7px;
            line-height: 1.1;
        ">{value}</div>
        {sub}
    </div>
    """


def _render_row(cards: list[tuple]) -> None:
    """Ряд карточек. cards = [(label, value, subtitle, color), ...]."""
    cols = st.columns(len(cards))
    for col, (label, value, sub, color) in zip(cols, cards):
        with col:
            st.markdown(
                _card(label, value, sub, color),
                unsafe_allow_html=True,
            )


def render(filtered: pd.DataFrame, results: pd.DataFrame) -> None:
    st.markdown(
        '<div class="hands-title">Профиль игрока</div>',
        unsafe_allow_html=True,
    )

    # ============================================================
    # Данные
    # ============================================================
    if len(filtered) == 0:
        st.warning("Нет данных по текущим фильтрам")
        return

    bb_val = bb_per_100(filtered)
    total_hands = len(filtered)

    rdf = results[results["currency"] != "SAT"].copy()
    rdf = rdf[rdf["buyin_total"] > 0]
    total_tournaments = len(rdf)

    if total_tournaments > 0:
        total_cost = float(rdf["cost"].sum())
        total_payout = float(rdf["payout"].sum())
        profit_usd = total_payout - total_cost
        roi = (profit_usd / total_cost * 100) if total_cost > 0 else 0.0
        itm_pct = float(rdf["itm"].mean()) * 100
        best_tournament = float(rdf["profit"].max())
        avg_buyin = float(rdf["buyin_total"].mean())
    else:
        total_cost = total_payout = profit_usd = roi = itm_pct = 0.0
        best_tournament = avg_buyin = 0.0

    preflop = _compute_preflop_stats()

    avg_stack = float(filtered["stack_bb"].mean())
    med_stack = float(filtered["stack_bb"].median())
    avg_level = float(filtered["level"].mean())

    # ============================================================
    # Ключевые метрики
    # ============================================================
    st.markdown("### Ключевые метрики")

    bb_color = "#2ecc71" if bb_val >= 0 else "#e74c3c"
    roi_color = "#2ecc71" if roi >= 0 else "#e74c3c"
    profit_color = "#2ecc71" if profit_usd >= 0 else "#e74c3c"

    _render_row([
        ("bb / 100", f"{bb_val:+.2f}", "винрейт на 100 раздач", bb_color),
        ("ROI", f"{roi:+.1f}%", f"профит ${profit_usd:+,.2f}", roi_color),
        ("Турниров", f"{total_tournaments:,}", f"средний бай-ин ${avg_buyin:.2f}", "#0f172a"),
        ("Раздач", f"{total_hands:,}", "по фильтрам", "#0f172a"),
    ])

    # ============================================================
    # Результаты
    # ============================================================
    st.markdown("### Результаты")

    itm_color = "#2ecc71" if itm_pct >= 15 else "#f39c12" if itm_pct >= 10 else "#e74c3c"
    best_color = "#2ecc71" if best_tournament > 0 else "#94a3b8"

    _render_row([
        ("ITM", f"{itm_pct:.1f}%", "попадание в призы", itm_color),
        ("Профит", f"${profit_usd:+,.2f}", "чистый результат", profit_color),
        ("Выплаты", f"${total_payout:,.2f}", "всего получено", "#0f172a"),
        ("Затраты", f"${total_cost:,.2f}", "всего вложено", "#0f172a"),
    ])

    _render_row([
        ("Лучший турнир", f"${best_tournament:+,.2f}", "по профиту", best_color),
        ("ITM-турниров", f"{int(rdf['itm'].sum()) if len(rdf) else 0}",
         "попаданий в деньги", "#0f172a"),
        ("Средний ROI", f"{roi:+.1f}%",
         "за период", roi_color),
        ("Средний ITM", f"{itm_pct:.1f}%",
         "за период", itm_color),
    ])

    # ============================================================
    # Игровой стиль
    # ============================================================
    st.markdown("### Игровой стиль")

    _render_row([
        ("VPIP", f"{preflop['vpip']:.1f}%",
         "добровольно в банк", "#3b82f6"),
        ("PFR", f"{preflop['pfr']:.1f}%",
         "рейз префлоп", "#8b5cf6"),
        ("3-bet", f"{preflop['threebet']:.1f}%",
         "ре-рейз префлоп", "#ec4899"),
        ("PFR / VPIP", f"{preflop['pfr']/max(preflop['vpip'], 0.01)*100:.0f}%",
         "агрессивность", "#0f172a"),
    ])

    # ============================================================
    # Стеки и уровни
    # ============================================================
    st.markdown("### Стеки и уровни")

    _render_row([
        ("Средний стек", f"{avg_stack:.1f} BB", "по фильтрам", "#0f172a"),
        ("Медиана стека", f"{med_stack:.1f} BB", "типичный размер", "#0f172a"),
        ("Средний уровень", f"{avg_level:.1f}", "стадия турнира", "#0f172a"),
        ("Раздач в выборке", f"{total_hands:,}", "с учётом фильтров", "#0f172a"),
    ])