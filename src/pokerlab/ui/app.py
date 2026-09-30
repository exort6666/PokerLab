"""Точка входа Streamlit-дашборда."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pokerlab.ui.shared import load_hands, load_results
from pokerlab.ui.styles import inject_css

st.set_page_config(
    page_title="PokerLab",
    layout="wide",
    page_icon="♠",
)
inject_css()


# ============================================================
# Данные
# ============================================================

df = load_hands()
results = load_results()


# ============================================================
# Компонент фильтров
# ============================================================

def render_filters(df: pd.DataFrame, prefix: str = "") -> pd.DataFrame:
    """Панель фильтров. prefix — уникальный для каждой вкладки."""

    with st.container(key=f"filters_{prefix}"):
        st.markdown(
            '<div class="filter-card-title">'
            '<div class="filter-card-icon">⚙</div>'
            '<div class="filter-card-title-text">Фильтры</div>'
            '</div>',
            unsafe_allow_html=True,
        )

        c1, c2, c3, c4 = st.columns([1.2, 1.2, 1.2, 2])

        zone = c1.radio(
            "Зона",
            options=["Все", "ChipEV", "ICM"],
            index=0,
            key=f"{prefix}_zone",
        )

        level_min = int(df["level"].min())
        level_max = int(df["level"].max())
        level_range = c2.slider(
            "Уровень",
            min_value=level_min, max_value=level_max,
            value=(level_min, level_max),
            key=f"{prefix}_level",
        )

        stack_max = float(min(df["stack_bb"].max(), 300.0))
        stack_range = c3.slider(
            "Стек (BB)",
            min_value=0.0, max_value=stack_max,
            value=(0.0, stack_max),
            key=f"{prefix}_stack",
        )

        positions = sorted(df["hero_position"].dropna().unique().tolist())
        selected_positions = c4.multiselect(
            "Позиции",
            options=positions, default=positions,
            key=f"{prefix}_pos",
        )

    mask = (
        df["level"].between(*level_range)
        & df["stack_bb"].between(*stack_range)
        & df["hero_position"].isin(selected_positions)
    )
    if zone == "ChipEV":
        mask &= df["level"] <= 12
    elif zone == "ICM":
        mask &= df["level"] >= 13

    return df[mask].copy()


# ============================================================
# Вкладки
# ============================================================

tab_labels = [
    "Обзор",
    "Раздачи",
    "Расписание",
    "Расчёты",
    "HU Review",
    "Результаты",
]
(
    tab_overview,
    tab_hands,
    tab_schedule,
    tab_analysis,
    tab_hu,
    tab_results,
) = st.tabs(tab_labels)


# ============================================================
# Рендер
# ============================================================

from pokerlab.ui.tabs import (  # noqa: E402
    overview as tab_overview_mod,
    hands as tab_hands_mod,
    schedule as tab_schedule_mod,
    analysis as tab_analysis_mod,
    hu_review as tab_hu_mod,
    results as tab_results_mod,
)

with tab_overview:
    filtered = render_filters(df, prefix="ov")
    tab_overview_mod.render(filtered, results)

with tab_hands:
    filtered = render_filters(df, prefix="hn")
    tab_hands_mod.render(filtered)

with tab_schedule:
    tab_schedule_mod.render(results)

with tab_analysis:
    tab_analysis_mod.render(results)
with tab_hu:
    tab_hu_mod.render()
with tab_results:
    tab_results_mod.render(results)