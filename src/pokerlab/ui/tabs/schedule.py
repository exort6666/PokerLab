"""Вкладка «Расписание» — по дням недели, с периодом и топ-часами."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pokerlab.analysis.classify import classify_type, day_of_week_name
from pokerlab.ui.shared import (
    COLOR_CONTINUOUS,
    filter_by_period,
    style_bar,
)


DAYS_ORDER = [
    "Понедельник", "Вторник", "Среда", "Четверг",
    "Пятница", "Суббота", "Воскресенье",
]


def render(results: pd.DataFrame) -> None:
    st.markdown(
        '<div class="hands-title">Расписание по дням недели</div>',
        unsafe_allow_html=True,
    )
    period = st.radio(
        "Период",
        options=["Всё время", "Год", "Месяц", "Неделя", "День"],
        index=0,
        horizontal=True,
        key="sched_period",
    )

    sdf = results[results["currency"] != "SAT"].copy()
    sdf = sdf[sdf["buyin_total"] > 0].copy()
    sdf = sdf.dropna(subset=["started_at"]).copy()
    sdf = filter_by_period(sdf, period)

    if len(sdf) == 0:
        st.warning("Нет данных за выбранный период")
        return

    ref_date = sdf["started_at"].max().strftime("%Y-%m-%d")
    st.caption(
        f"Период: **{period}**. Последний турнир: **{ref_date}**. "
        f"Турниров в выборке: **{len(sdf)}**."
    )

    sdf["type"] = sdf["tournament_name"].apply(classify_type)
    sdf["dow"] = sdf["started_at"].dt.dayofweek
    sdf["hour"] = sdf["started_at"].dt.hour
    sdf["day"] = sdf["dow"].apply(lambda x: day_of_week_name(int(x)))
    sdf["buyin"] = sdf["buyin_total"].round(2)

    sched = (
        sdf.groupby(["day", "dow", "hour", "type", "buyin"])
        .agg(
            tournaments=("tournament_id", "count"),
            cost=("cost", "sum"),
            payout=("payout", "sum"),
            itm_count=("itm", "sum"),
        )
        .reset_index()
    )
    sched["profit"] = sched["payout"] - sched["cost"]
    sched["roi_pct"] = (
        sched["profit"] / sched["cost"] * 100
    ).where(sched["cost"] > 0, 0)
    sched["itm_pct"] = sched["itm_count"] / sched["tournaments"] * 100
    sched = sched.sort_values(["dow", "hour", "buyin"])

    _render_summary(sched)
    _render_best_hours(sdf)
    st.divider()
    _render_daily_tables(sched)


def _render_summary(sched: pd.DataFrame) -> None:
    st.subheader("Сводка по дням")

    by_day = (
        sched.groupby(["day", "dow"])
        .agg(tournaments=("tournaments", "sum"),
             profit=("profit", "sum"))
        .reset_index()
        .sort_values("dow")
    )

    fig = px.bar(
        by_day, x="day", y="profit",
        color="profit", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"day": "День недели", "profit": "Профит ($)"},
        text="profit",
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    style_bar(fig, height=400)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_best_hours(sdf: pd.DataFrame) -> None:
    st.subheader("⏰ Лучшее время для старта")

    by_hour = (
        sdf.groupby("hour")
        .agg(
            tournaments=("tournament_id", "count"),
            cost=("cost", "sum"),
            payout=("payout", "sum"),
        )
        .reset_index()
    )
    by_hour["profit"] = by_hour["payout"] - by_hour["cost"]
    by_hour["roi_pct"] = (
        by_hour["profit"] / by_hour["cost"] * 100
    ).where(by_hour["cost"] > 0, 0)
    by_hour["hour_str"] = by_hour["hour"].apply(lambda h: f"{int(h):02d}:00")

    filtered_hours = by_hour[by_hour["tournaments"] >= 2].copy()
    filtered_hours = filtered_hours.sort_values("profit", ascending=False)

    if len(filtered_hours) == 0:
        st.info("Мало данных для анализа по часам")
        return

    col_best, col_worst = st.columns(2)

    with col_best:
        st.markdown("**🟢 Топ-5 лучших часов**")
        top5 = filtered_hours.head(5)[
            ["hour_str", "tournaments", "profit", "roi_pct"]
        ].rename(columns={
            "hour_str": "Час", "tournaments": "Турниров",
            "profit": "Профит ($)", "roi_pct": "ROI (%)",
        })
        top5["Профит ($)"] = top5["Профит ($)"].round(2)
        top5["ROI (%)"] = top5["ROI (%)"].round(1)
        st.dataframe(top5, width="stretch", hide_index=True)

    with col_worst:
        st.markdown("**🔴 Топ-5 худших часов**")
        worst5 = filtered_hours.tail(5)[
            ["hour_str", "tournaments", "profit", "roi_pct"]
        ].rename(columns={
            "hour_str": "Час", "tournaments": "Турниров",
            "profit": "Профит ($)", "roi_pct": "ROI (%)",
        })
        worst5["Профит ($)"] = worst5["Профит ($)"].round(2)
        worst5["ROI (%)"] = worst5["ROI (%)"].round(1)
        st.dataframe(worst5, width="stretch", hide_index=True)

    hour_chart = filtered_hours.sort_values("hour_str")
    fig = px.bar(
        hour_chart, x="hour_str", y="profit",
        color="profit", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"hour_str": "Час", "profit": "Профит ($)"},
        text="profit",
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    style_bar(fig, height=400)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)


def _render_daily_tables(sched: pd.DataFrame) -> None:
    st.subheader("📆 Детальное расписание по дням")

    for day_name in DAYS_ORDER:
        day_data = sched[sched["day"] == day_name].copy()
        if len(day_data) == 0:
            continue

        day_profit = day_data["profit"].sum()
        day_tournaments = day_data["tournaments"].sum()

        if day_profit > 50:
            emoji = "🟢"
        elif day_profit > 0:
            emoji = "🟡"
        else:
            emoji = "🔴"

        st.subheader(
            f"{emoji} {day_name} — {day_tournaments} турниров, "
            f"профит ${day_profit:+.2f}"
        )

        day_display = day_data.copy()
        day_display["Время"] = day_display["hour"].apply(
            lambda h: f"{int(h):02d}:00"
        )
        day_display = day_display.rename(columns={
            "type": "Тип", "buyin": "Бай-ин ($)",
            "tournaments": "Турниров", "itm_pct": "ITM (%)",
            "roi_pct": "ROI (%)", "profit": "Профит ($)",
        })[["Время", "Тип", "Бай-ин ($)", "Турниров",
            "ITM (%)", "ROI (%)", "Профит ($)"]]

        def color_day_row(row) -> list[str]:
            if row["Профит ($)"] > 0:
                return ["background-color: #d4edda"] * len(row)
            if row["Профит ($)"] == 0:
                return ["background-color: #eeeeee"] * len(row)
            return ["background-color: #f8d7da"] * len(row)

        styled = day_display.style.apply(color_day_row, axis=1).format({
            "Бай-ин ($)": "{:.2f}",
            "ITM (%)": "{:.1f}",
            "ROI (%)": "{:+.1f}",
            "Профит ($)": "{:+.2f}",
        })
        st.dataframe(styled, width="stretch", hide_index=True)
        st.write("")