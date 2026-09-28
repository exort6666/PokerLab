"""Вкладка «Турниры» — сводка по турнирам с фильтрами."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pokerlab.ui.shared import (
    COLOR_CONTINUOUS,
    GREEN,
    color_row,
    style_bar,
    style_line,
)


def render(filtered: pd.DataFrame, results: pd.DataFrame) -> None:
    st.title("Турниры")

    by_tour_hands = (
        filtered.groupby("tournament_id")
        .agg(hands=("id", "count"), net_bb=("net_bb", "sum"),
             bb_sum=("bb", "sum"))
        .reset_index()
    )
    by_tour_hands["bb_per_100"] = (
        by_tour_hands["net_bb"]
        / (by_tour_hands["bb_sum"] / by_tour_hands["hands"])
        / by_tour_hands["hands"] * 100
    )

    merged = results.merge(
        by_tour_hands[["tournament_id", "hands", "bb_per_100"]],
        on="tournament_id", how="left",
    )
    merged["hands"] = merged["hands"].fillna(0).astype(int)

    # Фильтры
    fcol1, fcol2, fcol3 = st.columns(3)

    currencies = sorted(merged["currency"].unique().tolist())
    selected_currencies = fcol1.multiselect(
        "Валюты", options=currencies,
        default=[c for c in currencies if c != "SAT"],
    )

    max_buyin = (
        float(merged["buyin_total"].max()) if len(merged) else 100.0
    )
    buyin_range = fcol2.slider(
        "Бай-ин ($)", min_value=0.0, max_value=max_buyin,
        value=(0.0, max_buyin),
    )

    exclude_sat = fcol3.checkbox("Исключить сателлиты (SAT)", value=True)

    tmask = (
        merged["currency"].isin(selected_currencies)
        & merged["buyin_total"].between(*buyin_range)
    )
    if exclude_sat:
        tmask &= merged["currency"] != "SAT"

    tfilt = merged[tmask].copy()

    if len(tfilt) == 0:
        st.warning("Нет данных по фильтрам")
        return

    # Сводка
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Турниров", f"{len(tfilt):,}")
    itm = tfilt["itm"].sum()
    col2.metric("ITM", f"{itm} ({itm/len(tfilt)*100:.1f}%)")
    col3.metric("Затраты", f"${tfilt['cost'].sum():,.2f}")
    col4.metric("Выплаты", f"${tfilt['payout'].sum():,.2f}")
    profit = tfilt["profit"].sum()
    cost = tfilt["cost"].sum()
    roi = (profit / cost * 100) if cost else 0
    col5.metric("ROI", f"{roi:+.1f}%")

    _render_by_buyin(tfilt)
    _render_timeline(tfilt)
    _render_table(tfilt)


def _render_by_buyin(tfilt: pd.DataFrame) -> None:
    def bucket_buyin(b: float) -> str:
        if b <= 1.20:
            return "до $1.20"
        if b <= 2.60:
            return "$1.21–$2.60"
        if b <= 3.30:
            return "$2.61–$3.30"
        if b <= 5.50:
            return "$3.31–$5.50"
        return "выше $5.50"

    tfilt = tfilt.copy()
    tfilt["buyin_bucket"] = tfilt["buyin_total"].apply(bucket_buyin)
    by_b = (
        tfilt.groupby("buyin_bucket")
        .agg(
            tournaments=("tournament_id", "count"),
            cost=("cost", "sum"),
            payout=("payout", "sum"),
            profit=("profit", "sum"),
        )
        .reset_index()
    )
    by_b["roi_pct"] = (
        by_b["profit"] / by_b["cost"] * 100
    ).where(by_b["cost"] > 0, 0)
    by_b = by_b.sort_values("buyin_bucket")

    fig = px.bar(
        by_b, x="buyin_bucket", y="roi_pct",
        color="roi_pct", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"buyin_bucket": "Бай-ин", "roi_pct": "ROI, %"},
        text="roi_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}%", textposition="outside")
    style_bar(fig, height=420)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_timeline(tfilt: pd.DataFrame) -> None:
    st.subheader("Кумулятивный профит ($) по времени")

    timeline_df = tfilt.dropna(subset=["started_at"]).sort_values("started_at")
    if len(timeline_df) == 0:
        st.info("Нет данных по времени")
        return

    timeline_df = timeline_df.copy()
    timeline_df["cum_profit"] = timeline_df["profit"].cumsum()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=timeline_df["started_at"],
        y=timeline_df["cum_profit"],
        mode="lines+markers",
        line=dict(color=GREEN, width=3),
        marker=dict(size=6, color=GREEN,
                    line=dict(width=1, color="black")),
        fill="tozeroy",
        fillcolor="rgba(46, 204, 113, 0.15)",
    ))
    style_line(fig, height=460)
    fig.update_layout(
        xaxis_title="Дата",
        yaxis_title="Кумулятивный профит ($)",
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_table(tfilt: pd.DataFrame) -> None:
    st.subheader("Все турниры")

    table = tfilt.sort_values(
        "started_at", ascending=False, na_position="last"
    )[[
        "tournament_name", "buyin_total", "field_size",
        "hero_place", "payout", "profit", "roi_pct",
        "hands", "bb_per_100",
    ]].copy().rename(columns={
        "tournament_name": "Турнир",
        "buyin_total": "Бай-ин ($)",
        "field_size": "Поле",
        "hero_place": "Место",
        "payout": "Призы ($)",
        "profit": "Профит ($)",
        "roi_pct": "ROI (%)",
        "hands": "Рук",
        "bb_per_100": "bb/100",
    })

    for c in ["Бай-ин ($)", "Призы ($)", "Профит ($)"]:
        table[c] = table[c].round(2)
    table["ROI (%)"] = table["ROI (%)"].round(1)
    table["bb/100"] = table["bb/100"].round(1)

    styled = table.style.apply(color_row, axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)