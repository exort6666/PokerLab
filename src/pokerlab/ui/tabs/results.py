"""Вкладка «Результаты» — деньги по времени."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from pokerlab.ui.shared import (
    GREEN,
    filter_by_period,
    style_line,
)


PERIODS = ["День", "Неделя", "Месяц", "Полгода", "Год", "Всё время"]


def render(results: pd.DataFrame) -> None:
    st.markdown(
        '<div class="hands-title">Результаты</div>',
        unsafe_allow_html=True,
    )

    # Оставляем только реальные турниры
    df = results[results["currency"] != "SAT"].copy()
    df = df[df["buyin_total"] > 0].copy()
    df = df.dropna(subset=["started_at"]).copy()
    df = df.sort_values("started_at").reset_index(drop=True)

    if len(df) == 0:
        st.warning("Нет данных")
        return

    period = st.radio(
        "Период",
        options=PERIODS,
        index=2,  # Месяц по умолчанию
        horizontal=True,
        key="results_period",
    )

    sdf = _filter_by_results_period(df, period)
    if len(sdf) == 0:
        st.warning("Нет данных за выбранный период")
        return

    # Сводка
    _render_metrics(sdf, period)

    # Кумулятивный график
    _render_cumulative(sdf)


def _filter_by_results_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Фильтр от максимальной даты."""
    if period == "Всё время" or len(df) == 0:
        return df
    ref = df["started_at"].max()
    days = {
        "День": 1,
        "Неделя": 7,
        "Месяц": 30,
        "Полгода": 182,
        "Год": 365,
    }.get(period)
    if days is None:
        return df
    cutoff = ref - pd.Timedelta(days=days)
    return df[df["started_at"] >= cutoff]


def _render_metrics(df: pd.DataFrame, period: str) -> None:
    cost = float(df["cost"].sum())
    payout = float(df["payout"].sum())
    profit = payout - cost
    roi = (profit / cost * 100) if cost > 0 else 0.0
    itm = int(df["itm"].sum())
    n = len(df)
    itm_pct = itm / n * 100 if n > 0 else 0.0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Турниров", f"{n:,}")
    c2.metric("Затраты", f"${cost:,.2f}")
    c3.metric("Выплаты", f"${payout:,.2f}")
    c4.metric("Профит", f"${profit:+,.2f}")
    c5.metric("ROI", f"{roi:+.1f}%")

    c6, c7, c8, c9, c10 = st.columns(5)
    c6.metric("ITM", f"{itm} ({itm_pct:.1f}%)")
    if len(df) > 0:
        best = float(df["profit"].max())
        worst = float(df["profit"].min())
        avg = float(df["profit"].mean())
        med = float(df["profit"].median())
    else:
        best = worst = avg = med = 0.0
    c7.metric("Лучший турнир", f"${best:+,.2f}")
    c8.metric("Худший турнир", f"${worst:+,.2f}")
    c9.metric("Средний", f"${avg:+,.2f}")
    c10.metric("Медиана", f"${med:+,.2f}")

    ref_date = df["started_at"].max().strftime("%Y-%m-%d")
    st.caption(f"Период: {period}. Последний турнир: {ref_date}.")


def _render_cumulative(df: pd.DataFrame) -> None:
    st.subheader("Кумулятивный профит")

    timeline = df.sort_values("started_at").copy()
    timeline["cum_profit"] = timeline["profit"].cumsum()

    final = timeline["cum_profit"].iloc[-1]
    line_color = GREEN if final >= 0 else "#e74c3c"
    fill_color = (
        "rgba(46, 204, 113, 0.15)" if final >= 0
        else "rgba(231, 76, 60, 0.15)"
    )

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline["started_at"],
        y=timeline["cum_profit"],
        mode="lines",
        line=dict(color=line_color, width=3),
        fill="tozeroy",
        fillcolor=fill_color,
        hovertemplate="%{x|%Y-%m-%d %H:%M}<br>"
                      "Кумулятивный профит: $%{y:,.2f}<extra></extra>",
    ))
    # Горизонтальная линия нуля
    fig.add_hline(
        y=0, line=dict(color="#888", width=1, dash="dash"),
    )
    style_line(fig, height=520)
    fig.update_layout(
        xaxis_title="Дата",
        yaxis_title="Кумулятивный профит ($)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# Совместимость со старым импортом
def render_timeline(filtered: pd.DataFrame) -> None:
    """DEPRECATED. Используй render(results)."""
    pass