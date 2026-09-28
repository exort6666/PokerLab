"""Интерактивная вкладка Push/Fold в Streamlit."""

from __future__ import annotations

import time

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from pokerlab.mtt.cfr_pushfold import (
    ALL_HANDS, N_HANDS, compute_pushfold_cfr,
)
from pokerlab.mtt.pko_3max import compute_pushfold_pko_3max


_RANK_ORDER = "AKQJT98765432"


def _hands_to_grid(hands: list[str]) -> np.ndarray:
    """169 руки в матрицу 13×13.
    Строки и столбцы: A K Q J T 9 8 7 6 5 4 3 2.
    Верхний треугольник (i<j) — suited.
    Нижний (i>j) — offsuit.
    Диагональ — пары.
    Значение: 1 если рука в диапазоне, 0 иначе.
    """
    grid = np.zeros((13, 13), dtype=float)
    for h in hands:
        r1 = h[0]
        r2 = h[1]
        i = _RANK_ORDER.index(r1)
        j = _RANK_ORDER.index(r2)
        if r1 == r2:
            grid[i, j] = 1.0
        elif h.endswith("s"):
            # suited — верхний треугольник
            if i < j:
                grid[i, j] = 1.0
            else:
                grid[j, i] = 1.0
        else:
            # offsuit — нижний треугольник
            if i > j:
                grid[i, j] = 1.0
            else:
                grid[j, i] = 1.0
    return grid


def _hand_label(i: int, j: int) -> str:
    r1 = _RANK_ORDER[i]
    r2 = _RANK_ORDER[j]
    if i == j:
        return r1 + r2
    if i < j:
        return f"{r1}{r2}s"
    return f"{r2}{r1}o"


def _count_combos(hands: list[str]) -> int:
    total = 0
    for h in hands:
        if h[0] == h[1]:
            total += 6
        elif h.endswith("s"):
            total += 4
        else:
            total += 12
    return total


def _range_chart(hands: list[str], title: str, color: str) -> go.Figure:
    grid = _hands_to_grid(hands)
    labels = [
        [_hand_label(i, j) for j in range(13)]
        for i in range(13)
    ]
    fig = go.Figure(data=go.Heatmap(
        z=grid,
        x=list(_RANK_ORDER),
        y=list(_RANK_ORDER),
        colorscale=[[0, "#f8f8f8"], [1, color]],
        showscale=False,
        text=labels,
        texttemplate="%{text}",
        textfont={"size": 10, "color": "#222"},
        hovertemplate="%{text}<extra></extra>",
    ))
    fig.update_layout(
        title=title,
        height=560,
        width=560,
        yaxis=dict(autorange="reversed"),
        xaxis=dict(side="top"),
        font=dict(size=12),
        margin=dict(l=20, r=20, t=50, b=20),
    )
    return fig


def render_pushfold_tab() -> None:
    st.title("🎯 Push/Fold Solver")

    mode = st.radio(
        "Режим",
        ["HU chipEV (SB vs BB)", "3-max PKO (BTN/SB/BB)"],
        horizontal=True,
        key="pf_mode",
    )

    if mode == "HU chipEV (SB vs BB)":
        c1, c2, c3 = st.columns(3)
        stack = c1.number_input(
            "Стек (BB)", min_value=1.0, max_value=100.0,
            value=15.0, step=1.0, key="pf_hu_stack",
        )
        ante = c2.number_input(
            "Анте (BB)", min_value=0.0, max_value=5.0,
            value=0.1, step=0.1, key="pf_hu_ante",
        )
        players = c3.number_input(
            "Игроков", min_value=2, max_value=9,
            value=8, step=1, key="pf_hu_players",
        )

        if st.button("Рассчитать", key="pf_hu_go"):
            with st.spinner("CFR+ считает..."):
                t0 = time.time()
                result = compute_pushfold_cfr(
                    stack_bb=float(stack),
                    ante_bb=float(ante),
                    players=int(players),
                    iterations=20_000,
                )
                elapsed = time.time() - t0

            col_l, col_r = st.columns(2)
            with col_l:
                fig = _range_chart(
                    result.push_range,
                    f"SB Push — {len(result.push_range)} рук "
                    f"({_count_combos(result.push_range)/1326*100:.1f}%)",
                    "#2ecc71",
                )
                st.plotly_chart(fig, use_container_width=False)
            with col_r:
                fig = _range_chart(
                    result.call_range,
                    f"BB Call — {len(result.call_range)} рук "
                    f"({_count_combos(result.call_range)/1326*100:.1f}%)",
                    "#e74c3c",
                )
                st.plotly_chart(fig, use_container_width=False)

            st.caption(
                f"Стек: {stack} BB | Анте: {ante} | Игроков: {players} | "
                f"Exploitability: {result.exploitability:.6f} | "
                f"Время: {elapsed:.1f} сек"
            )

    else:  # 3-max PKO
        c1, c2, c3, c4 = st.columns(4)
        stack = c1.number_input(
            "Стек (BB)", min_value=1.0, max_value=50.0,
            value=15.0, step=1.0, key="pf_3m_stack",
        )
        b_btn = c2.number_input(
            "Bounty BTN ($)", min_value=0.0, max_value=100.0,
            value=1.5, step=0.5, key="pf_3m_bbtn",
        )
        b_sb = c3.number_input(
            "Bounty SB ($)", min_value=0.0, max_value=100.0,
            value=1.5, step=0.5, key="pf_3m_bsb",
        )
        b_bb = c4.number_input(
            "Bounty BB ($)", min_value=0.0, max_value=100.0,
            value=1.5, step=0.5, key="pf_3m_bbb",
        )

        c5, c6, c7 = st.columns(3)
        p1 = c5.number_input(
            "P1 ($)", min_value=0.0, value=30.0, step=1.0, key="pf_3m_p1",
        )
        p2 = c6.number_input(
            "P2 ($)", min_value=0.0, value=30.0, step=1.0, key="pf_3m_p2",
        )
        p3 = c7.number_input(
            "P3 ($)", min_value=0.0, value=0.0, step=1.0, key="pf_3m_p3",
        )

        if st.button("Рассчитать", key="pf_3m_go"):
            with st.spinner("CFR+ 3-max считает..."):
                t0 = time.time()
                result = compute_pushfold_pko_3max(
                    stack_bb=float(stack),
                    bounties=(float(b_btn), float(b_sb), float(b_bb)),
                    prizes=(float(p1), float(p2), float(p3)),
                    iterations=2000,
                )
                elapsed = time.time() - t0

            ranges = [
                ("BTN Push", result["btn_push"], "#3498db"),
                ("SB Push (after BTN fold)",
                 result["sb_push_after_btnfold"], "#2ecc71"),
                ("SB Call (vs BTN push)",
                 result["sb_call_after_btnpush"], "#9b59b6"),
                ("BB Call (vs SB push)",
                 result["bb_call_after_sbpush"], "#e74c3c"),
                ("BB Call (vs BTN push, SB fold)",
                 result["bb_call_after_btnpush_sbfold"], "#e67e22"),
            ]

            for title, hands, color in ranges:
                combos = _count_combos(hands)
                pct = combos / 1326 * 100
                fig = _range_chart(
                    hands, f"{title} — {len(hands)} рук ({pct:.1f}%)", color,
                )
                st.plotly_chart(fig, use_container_width=False)

            st.caption(
                f"Стек: {stack} BB | Bounties: BTN ${b_btn}, "
                f"SB ${b_sb}, BB ${b_bb} | Призы: ${p1}/${p2}/${p3} | "
                f"Время: {elapsed:.1f} сек"
            )