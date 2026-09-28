"""Вкладка «Push/Fold» — интерактивный GTO-калькулятор."""

from __future__ import annotations

import time

import streamlit as st

from pokerlab.mtt.cfr_pushfold import compute_pushfold_cfr
from pokerlab.mtt.pko_3max import compute_pushfold_pko_3max


_RANK_ORDER = "AKQJT98765432"


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


def _range_html(
    hands: list[str],
    title: str,
    color: str,
) -> str:
    """
    13×13 HTML-таблица диапазона.
    A в левом верхнем углу, 2 в правом нижнем.
    Диагональ: AA, KK, ..., 22.
    Верхний правый треугольник — suited.
    Нижний левый — offsuit.
    """
    hand_set = set(hands)

    # Стили
    cell_size = "44px"
    border = "1px solid #333"
    font = "font-family: Arial; font-size: 11px; text-align: center;"

    html: list[str] = []
    html.append(
        f'<div style="margin: 10px 0;">'
        f'<div style="font-size: 15px; font-weight: bold; '
        f'margin-bottom: 8px;">{title}</div>'
        f'<table style="border-collapse: collapse; {font}">'
    )

    # Заголовок столбцов (пустая ячейка + A K Q J T 9 8 7 6 5 4 3 2)
    html.append('<tr>')
    html.append(
        f'<td style="width: {cell_size}; height: {cell_size}; '
        f'border: {border}; background: #fafafa;"></td>'
    )
    for r in _RANK_ORDER:
        html.append(
            f'<td style="width: {cell_size}; height: {cell_size}; '
            f'border: {border}; background: #fafafa; '
            f'font-weight: bold; font-size: 13px;">{r}</td>'
        )
    html.append('</tr>')

    # Строки данных
    for i, r1 in enumerate(_RANK_ORDER):
        html.append('<tr>')
        # Заголовок строки
        html.append(
            f'<td style="width: {cell_size}; height: {cell_size}; '
            f'border: {border}; background: #fafafa; '
            f'font-weight: bold; font-size: 13px;">{r1}</td>'
        )

        for j, r2 in enumerate(_RANK_ORDER):
            if i == j:
                label = f"{r1}{r2}"
            elif i < j:
                label = f"{r1}{r2}s"
            else:
                label = f"{r2}{r1}o"

            in_range = label in hand_set

            if in_range:
                bg = color
                fg = "#ffffff"
                fw = "bold"
            else:
                bg = "#f0f0f0"
                fg = "#555"
                fw = "normal"

            html.append(
                f'<td style="width: {cell_size}; height: {cell_size}; '
                f'border: {border}; background: {bg}; color: {fg}; '
                f'font-weight: {fw}; font-size: 11px;">{label}</td>'
            )

        html.append('</tr>')

    html.append('</table></div>')
    return "".join(html)


def _show_range(hands: list[str], title: str, color: str) -> None:
    combos = _count_combos(hands)
    pct = combos / 1326 * 100
    full_title = f"{title} — {len(hands)} рук ({pct:.1f}%)"
    html = _range_html(hands, full_title, color)
    st.markdown(html, unsafe_allow_html=True)


def render() -> None:
    st.markdown(
        '<div class="hands-title">Push/Fold Solver</div>',
        unsafe_allow_html=True,
    )

    mode = st.radio(
        "Режим",
        ["HU chipEV (SB vs BB)", "3-max PKO (BTN/SB/BB)"],
        horizontal=True,
        key="pf_mode",
    )

    if mode == "HU chipEV (SB vs BB)":
        _render_hu()
    else:
        _render_3max()


def _render_hu() -> None:
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
            _show_range(result.push_range, "SB Push", "#2ecc71")
        with col_r:
            _show_range(result.call_range, "BB Call", "#e74c3c")

        st.caption(
            f"Стек: {stack} BB | Анте: {ante} | Игроков: {players} | "
            f"Exploitability: {result.exploitability:.6f} | "
            f"Время: {elapsed:.1f} сек"
        )


def _render_3max() -> None:
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
            _show_range(hands, title, color)

        st.caption(
            f"Стек: {stack} BB | Bounties: BTN ${b_btn}, "
            f"SB ${b_sb}, BB ${b_bb} | Призы: ${p1}/${p2}/${p3} | "
            f"Время: {elapsed:.1f} сек"
        )