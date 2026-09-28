"""Вкладка «Классификация» — ROI по типам, форматам, дням, часам."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from pokerlab.analysis.classify import (
    classify_format,
    classify_type,
    day_of_week_name,
)
from pokerlab.ui.shared import COLOR_CONTINUOUS, style_bar


def _group_stats(df_in: pd.DataFrame, by: str) -> pd.DataFrame:
    g = (
        df_in.groupby(by)
        .agg(
            tournaments=("tournament_id", "count"),
            cost=("cost", "sum"),
            payout=("payout", "sum"),
            itm_count=("itm", "sum"),
        )
        .reset_index()
    )
    g["profit"] = g["payout"] - g["cost"]
    g["roi_pct"] = (g["profit"] / g["cost"] * 100).where(g["cost"] > 0, 0)
    g["itm_pct"] = g["itm_count"] / g["tournaments"] * 100
    return g


def render(results: pd.DataFrame) -> None:
    st.title("Классификация турниров")

    rdf = results[results["currency"] != "SAT"].copy()
    rdf = rdf[rdf["buyin_total"] > 0].copy()
    rdf["type"] = rdf["tournament_name"].apply(classify_type)
    rdf["format"] = rdf["tournament_name"].apply(classify_format)
    rdf["dow"] = rdf["started_at"].dt.dayofweek
    rdf["hour"] = rdf["started_at"].dt.hour

    _render_by_type(rdf)
    _render_by_format(rdf)
    _render_by_dow(rdf)
    _render_by_hour(rdf)


def _render_by_type(rdf: pd.DataFrame) -> None:
    st.subheader("ROI по типам турниров")
    by_type = _group_stats(rdf, "type")
    by_type = by_type[by_type["tournaments"] >= 3].sort_values("roi_pct")

    fig = px.bar(
        by_type, x="type", y="roi_pct",
        color="roi_pct", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"type": "Тип", "roi_pct": "ROI, %"},
        text="roi_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    style_bar(fig, height=500)
    fig.update_coloraxes(showscale=False)
    fig.update_xaxes(tickangle=-30)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_type.rename(columns={
            "type": "Тип", "tournaments": "Турниров",
            "cost": "Затраты ($)", "payout": "Выплаты ($)",
            "profit": "Профит ($)", "roi_pct": "ROI (%)",
            "itm_pct": "ITM (%)",
        })[["Тип", "Турниров", "ROI (%)", "Профит ($)", "ITM (%)"]],
        width="stretch", hide_index=True,
    )


def _render_by_format(rdf: pd.DataFrame) -> None:
    st.subheader("ROI по форматам")
    by_format = _group_stats(rdf, "format").sort_values("roi_pct")

    fig = px.bar(
        by_format, x="format", y="roi_pct",
        color="roi_pct", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"format": "Формат", "roi_pct": "ROI, %"},
        text="roi_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    style_bar(fig, height=380)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_format.rename(columns={
            "format": "Формат", "tournaments": "Турниров",
            "profit": "Профит ($)", "roi_pct": "ROI (%)",
            "itm_pct": "ITM (%)",
        })[["Формат", "Турниров", "ROI (%)", "Профит ($)", "ITM (%)"]],
        width="stretch", hide_index=True,
    )


def _render_by_dow(rdf: pd.DataFrame) -> None:
    st.subheader("ROI по дням недели")
    dow_df = rdf.dropna(subset=["started_at"]).copy()
    if len(dow_df) == 0:
        st.info("Нет данных по дням")
        return

    dow_df["dow_name"] = dow_df["dow"].apply(
        lambda x: day_of_week_name(int(x))
    )
    by_dow = _group_stats(dow_df, "dow_name")
    order = ["Понедельник", "Вторник", "Среда", "Четверг",
             "Пятница", "Суббота", "Воскресенье"]
    by_dow["__order"] = by_dow["dow_name"].apply(
        lambda x: order.index(x) if x in order else 99
    )
    by_dow = by_dow.sort_values("__order").drop(columns="__order")

    fig = px.bar(
        by_dow, x="dow_name", y="roi_pct",
        color="roi_pct", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"dow_name": "День", "roi_pct": "ROI, %"},
        text="roi_pct",
    )
    fig.update_traces(texttemplate="%{text:.1f}", textposition="outside")
    style_bar(fig, height=420)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        by_dow.rename(columns={
            "dow_name": "День", "tournaments": "Турниров",
            "profit": "Профит ($)", "roi_pct": "ROI (%)",
            "itm_pct": "ITM (%)",
        })[["День", "Турниров", "ROI (%)", "Профит ($)", "ITM (%)"]],
        width="stretch", hide_index=True,
    )


def _render_by_hour(rdf: pd.DataFrame) -> None:
    st.subheader("ROI по часам (серверное время)")
    hr_df = rdf.dropna(subset=["started_at"]).copy()
    if len(hr_df) == 0:
        st.info("Нет данных по часам")
        return

    hr_df["hour_str"] = hr_df["hour"].apply(lambda x: f"{int(x):02d}:00")
    by_hour = _group_stats(hr_df, "hour_str").sort_values("hour_str")

    fig = px.bar(
        by_hour, x="hour_str", y="roi_pct",
        color="roi_pct", color_continuous_scale=COLOR_CONTINUOUS,
        labels={"hour_str": "Час", "roi_pct": "ROI, %"},
        text="roi_pct",
    )
    fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
    style_bar(fig, height=440)
    fig.update_coloraxes(showscale=False)
    st.plotly_chart(fig, use_container_width=True)