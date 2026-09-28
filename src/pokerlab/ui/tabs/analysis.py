"""Вкладка «Расчёты» — результаты анализа раздач."""

from __future__ import annotations

import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from pokerlab.config import DB_PATH
from pokerlab.ui.shared import COLOR_CONTINUOUS, style_bar


SPOT_LABELS = {
    "PREFLOP_OPEN": "Префлоп: Открытие",
    "PREFLOP_VS_OPEN": "Префлоп: Против open",
    "PREFLOP_VS_PUSH": "Префлоп: Против push",
    "PREFLOP_HERO_PUSH": "Префлоп: Push Hero",
    "PREFLOP_3BET": "Префлоп: 3-bet",
    "PREFLOP_VS_3BET": "Префлоп: Против 3-bet",
    "POSTFLOP_SRP": "Постфлоп: SRP",
    "POSTFLOP_3BP": "Постфлоп: 3-bet pot",
    "POSTFLOP_4BP": "Постфлоп: 4-bet pot",
    "POSTFLOP_LIMP": "Постфлоп: Лимп-пот",
    "MULTIWAY": "Multiway",
    "UNKNOWN": "Не определено",
}


@st.cache_data
def _load_analysis() -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT
            a.hand_id, a.spot_type, a.street, a.solver_name, a.solver_version,
            a.hero_action, a.optimal_action, a.ev_optimal, a.ev_actual,
            a.ev_loss, a.is_correct, a.is_critical,
            h.tournament_id, h.hero_position, h.hero_cards,
            h.hero_net, h.bb, h.sb, h.ante, h.board, h.level,
            p.stack_start AS hero_stack
        FROM hand_analysis a
        JOIN hands h ON h.id = a.hand_id
        LEFT JOIN hand_players p ON p.hand_id = h.id AND p.is_hero = 1
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    df["stack_bb"] = df["hero_stack"] / df["bb"]
    df["net_bb"] = df["hero_net"] / df["bb"]
    df["spot_label"] = df["spot_type"].map(SPOT_LABELS).fillna(df["spot_type"])
    return df


def render(results: pd.DataFrame) -> None:
    st.markdown(
        '<div class="hands-title">Расчёты</div>',
        unsafe_allow_html=True,
    )

    df = _load_analysis()
    if len(df) == 0:
        st.warning("Нет данных анализа. Запусти классификацию спотов.")
        return

    _render_summary(df)
    _render_distribution(df)
    _render_hands_list(df)


def _render_summary(df: pd.DataFrame) -> None:
    """Верхняя строка метрик."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Всего спотов", f"{len(df):,}")
    col2.metric("Уникальных типов", f"{df['spot_type'].nunique()}")
    analyzed = df["optimal_action"].notna().sum()
    col3.metric("С EV-расчётом", f"{analyzed:,}")
    correct = df["is_correct"].sum()
    col4.metric("Ошибок", f"{int((~df['is_correct'].astype(bool)).sum()):,}")


def _render_distribution(df: pd.DataFrame) -> None:
    """Распределение по типам спотов."""
    st.markdown("### Распределение по типам")

    by_type = (
        df.groupby(["spot_type", "spot_label"])
        .agg(
            count=("hand_id", "count"),
            analyzed=("optimal_action", lambda s: s.notna().sum()),
        )
        .reset_index()
        .sort_values("count", ascending=False)
    )

    fig = px.bar(
        by_type, x="spot_label", y="count",
        color="count", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"spot_label": "Тип спота", "count": "Раздач"},
        text="count",
    )
    fig.update_traces(
        texttemplate="%{text:,}", textposition="outside",
    )
    style_bar(fig, height=460)
    fig.update_coloraxes(showscale=False)
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    # Таблица
    display = by_type.rename(columns={
        "spot_label": "Тип спота",
        "count": "Раздач",
        "analyzed": "С EV-расчётом",
    })[["Тип спота", "Раздач", "С EV-расчётом"]]
    st.dataframe(display, width="stretch", hide_index=True)


def _render_hands_list(df: pd.DataFrame) -> None:
    """Список раздач с фильтрами."""
    st.markdown("### Список раздач")

    c1, c2, c3 = st.columns([2, 1, 1])

    spot_options = sorted(df["spot_type"].unique().tolist())
    selected_spots = c1.multiselect(
        "Типы спотов",
        options=spot_options,
        default=spot_options,
    )

    analyzed_only = c2.checkbox("Только с EV", value=False)
    errors_only = c3.checkbox("Только ошибки", value=False)

    filtered = df[df["spot_type"].isin(selected_spots)].copy()
    if analyzed_only:
        filtered = filtered[filtered["optimal_action"].notna()]
    if errors_only:
        filtered = filtered[~filtered["is_correct"].astype(bool)]

    st.caption(f"Показано: {len(filtered):,} из {len(df):,}")

    n_rows = st.slider(
        "Сколько строк показать",
        min_value=100,
        max_value=min(20000, max(len(filtered), 100)),
        value=min(500, max(len(filtered), 100)),
        step=100,
        key="analysis_rows",
    )

    display_df = filtered.head(n_rows).copy()
    display_df["spot_short"] = display_df["spot_label"]
    display_df["stack_bb"] = display_df["stack_bb"].round(1)
    display_df["net_bb"] = display_df["net_bb"].round(2)

    if "hero_action" in display_df.columns:
        display_df["hero_action"] = display_df["hero_action"].fillna("—")
    if "optimal_action" in display_df.columns:
        display_df["optimal_action"] = display_df["optimal_action"].fillna("—")
    if "ev_loss" in display_df.columns:
        display_df["ev_loss"] = display_df["ev_loss"].apply(
            lambda v: f"{v:+.3f}" if pd.notna(v) else "—"
        )

    show = display_df[[
        "hand_id", "spot_short", "hero_position", "hero_cards",
        "stack_bb", "hero_action", "optimal_action", "ev_loss",
        "net_bb", "board",
    ]].rename(columns={
        "hand_id": "ID",
        "spot_short": "Спот",
        "hero_position": "Поз.",
        "hero_cards": "Карты",
        "stack_bb": "Стек",
        "hero_action": "Hero",
        "optimal_action": "Оптимум",
        "ev_loss": "Потеря (bb)",
        "net_bb": "Профит (bb)",
        "board": "Борд",
    })

    st.dataframe(show, width="stretch", hide_index=True)