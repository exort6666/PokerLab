"""Вкладка «Раздачи» — таблица раздач с деталями."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from pokerlab.ui.shared import load_hand_detail


def render(filtered: pd.DataFrame) -> None:
    if len(filtered) == 0:
        st.warning("Нет данных")
        return

    st.markdown(
        '<div class="hands-title">Раздачи</div>',
        unsafe_allow_html=True,
    )

    total = len(filtered)
    max_rows = min(100_000, total)
    default_rows = min(10_000, max_rows)

    st.markdown(
        '<div class="slider-label-centered">Сколько строк показать</div>',
        unsafe_allow_html=True,
    )

    n_rows = st.slider(
        "Сколько строк показать",
        min_value=100,
        max_value=max_rows,
        value=default_rows,
        step=100,
        label_visibility="collapsed",
    )

    st.markdown(
        f'<div class="hands-count">Показано '
        f'<b>{min(n_rows, total):,}</b> из '
        f'<b>{total:,}</b> раздач</div>',
        unsafe_allow_html=True,
    )

    display_df = (
        filtered.sort_values("played_at", ascending=False)
        .head(n_rows).copy()
    )
    display_df["blinds"] = (
        display_df["sb"].astype(str) + "/" +
        display_df["bb"].astype(str) +
        " (" + display_df["ante"].astype(str) + ")"
    )
    display_df["stack_bb"] = display_df["stack_bb"].round(1)
    display_df["net_bb"] = display_df["net_bb"].round(2)
    display_df["played_at"] = display_df["played_at"].dt.strftime(
        "%d.%m %H:%M"
    )
    display_df["result"] = display_df["net_bb"].apply(
        lambda v: f"{v:+.2f}" if v != 0 else "0"
    )

    display_cols = [
        "played_at", "tournament_name", "level", "blinds",
        "hero_position", "hero_cards", "stack_bb", "result",
        "board", "id",
    ]
    show_df = display_df[display_cols].rename(columns={
        "played_at": "Время",
        "tournament_name": "Турнир",
        "level": "Ур.",
        "blinds": "Блайнды",
        "hero_position": "Поз.",
        "hero_cards": "Карты",
        "stack_bb": "Стек",
        "result": "Профит (bb)",
        "board": "Борд",
        "id": "ID",
    })

    event = st.dataframe(
        show_df,
        width="stretch",
        hide_index=True,
        on_select="rerun",
        selection_mode="multi-row",
        column_config={
            "Время": st.column_config.TextColumn("Время", width="small"),
            "Турнир": st.column_config.TextColumn("Турнир", width="medium"),
            "Ур.": st.column_config.NumberColumn("Ур.", width="small"),
            "Блайнды": st.column_config.TextColumn("Блайнды", width="small"),
            "Поз.": st.column_config.TextColumn("Поз.", width="small"),
            "Карты": st.column_config.TextColumn("Карты", width="small"),
            "Стек": st.column_config.NumberColumn(
                "Стек", width="small", format="%.1f BB",
            ),
            "Профит (bb)": st.column_config.TextColumn(
                "Профит (bb)", width="small",
            ),
            "Борд": st.column_config.TextColumn("Борд", width="medium"),
            "ID": st.column_config.TextColumn("ID", width="small"),
        },
    )

    if len(event.selection.rows) == 1:
        idx = event.selection.rows[0]
        hand_id = display_df.iloc[idx]["id"]
        _render_hand_detail(hand_id)

    elif len(event.selection.rows) > 1:
        selected_ids = [display_df.iloc[i]["id"] for i in event.selection.rows]
        selected_df = filtered[filtered["id"].isin(selected_ids)]
        _render_multi_summary(selected_df, len(selected_ids))


def _render_multi_summary(df: pd.DataFrame, n_selected: int) -> None:
    """Сводка по выбранным раздачам."""
    st.divider()
    st.subheader(f"Выбрано: {n_selected} раздач")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Раздач", f"{len(df):,}")
    col2.metric("Профит (bb)", f"{df['net_bb'].sum():+.2f}")
    col3.metric("Средний профит", f"{df['net_bb'].mean():+.3f} bb")
    col4.metric("bb/100", f"{df['net_bb'].mean() * 100:+.2f}")


def _render_hand_detail(hand_id: str) -> None:
    detail = load_hand_detail(hand_id)
    h = detail["hand"]

    st.divider()
    st.subheader(f"Раздача {hand_id}")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Позиция Hero", h["hero_position"] or "—")
    col2.metric("Карты Hero", h["hero_cards"] or "—")
    col3.metric("Профит (bb)", f"{h['hero_net']/h['bb']:.2f}")
    col4.metric("Банк", f"{h['total_pot']:,}")

    st.write(
        f"**Турнир:** {h['tournament_id']} | "
        f"**Уровень:** {h['level']} | "
        f"**Блайнды:** {h['sb']}/{h['bb']} (анте {h['ante']})"
    )
    st.write(f"**Борд:** {h['board'] or '—'}")

    st.write("**Игроки:**")
    players_df = pd.DataFrame(detail["players"])
    players_df = players_df[
        ["seat", "name", "stack_start", "position", "cards", "is_hero"]
    ]
    st.dataframe(players_df, width="stretch", hide_index=True)

    st.write("**Действия:**")
    actions_df = pd.DataFrame(detail["actions"])
    actions_df = actions_df[
        ["street", "action_order", "player_name",
         "action", "amount", "amount_to", "is_all_in"]
    ]
    st.dataframe(actions_df, width="stretch", hide_index=True)