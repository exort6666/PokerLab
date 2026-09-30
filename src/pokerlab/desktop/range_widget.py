"""Canvas с 13×13 таблицей диапазона (адаптивный)."""

from __future__ import annotations

import tkinter as tk

from pokerlab.desktop.constants import PANEL, RANK_ORDER, TEXT
from pokerlab.desktop.utils import hand_label


class RangeCanvas(tk.Canvas):
    """
    Адаптивная таблица 13×13.
    Размер ячейки вычисляется из фактического размера canvas:
    таблица старается занять максимально возможную квадратную
    область под заголовком, с учётом места под метки рангов.
    """

    # Минимальные размеры, чтобы canvas участвовал в grid/pack
    # с адекватной шириной до первой конфигурации.
    MIN_W = 320
    MIN_H = 300

    def __init__(self, parent, title: str, **kwargs):
        super().__init__(parent, bg=PANEL, highlightthickness=0,
                         width=self.MIN_W, height=self.MIN_H,
                         **kwargs)
        self.title = title
        self._last_render_args = None
        self.bind("<Configure>", self._on_configure)

    def _on_configure(self, _event) -> None:
        # Перерисовываем при изменении размера, если уже есть данные.
        if self._last_render_args is not None:
            self.render(*self._last_render_args)

    def render(self, hands_in_range, color, highlight=None, freq=0.0):
        # Запоминаем аргументы, чтобы перерисовать при resize.
        self._last_render_args = (hands_in_range, color, highlight, freq)

        self.delete("all")

        w = self.winfo_width()
        h = self.winfo_height()
        if w < 50:
            w = self.MIN_W
        if h < 50:
            h = self.MIN_H

        header_h = 26
        pad = 4

        # Заголовок слева + частота справа, в одну строку
        self.create_text(8, header_h / 2 + 2, text=self.title, anchor="w",
                         fill=TEXT, font=("Segoe UI", 11, "bold"))
        self.create_text(w - 8, header_h / 2 + 2, text=f"{freq:.1f}%",
                         anchor="e", fill="#475569",
                         font=("Segoe UI", 11, "bold"))

        # Место под сетку: по каждой оси 13 ячеек + по 0.5 ячейки
        # на метки рангов сверху/слева → 14 "ячеек".
        avail_w = w - 2 * pad
        avail_h = h - header_h - 2 * pad
        if avail_w <= 0 or avail_h <= 0:
            return

        c = int(min(avail_w, avail_h) / 14)
        if c < 8:
            c = 8

        grid_size = c * 13
        # Центрируем квадратную сетку в доступной области
        ox = pad + (avail_w - grid_size) // 2
        oy = header_h + pad + (avail_h - grid_size) // 2

        # Шрифты масштабируются вместе с ячейкой
        cell_font_size = max(5, int(c * 0.36))
        header_font_size = max(6, int(c * 0.42))

        hand_set = set(hands_in_range)

        # Заголовки столбцов (сверху)
        for j, r in enumerate(RANK_ORDER):
            self.create_text(ox + j * c + c / 2, oy - c / 2,
                             text=r, fill=TEXT,
                             font=("Segoe UI", header_font_size, "bold"))

        # Ячейки + заголовки строк (слева)
        for i, r1 in enumerate(RANK_ORDER):
            self.create_text(ox - c / 2, oy + i * c + c / 2,
                             text=r1, fill=TEXT,
                             font=("Segoe UI", header_font_size, "bold"))
            for j, r2 in enumerate(RANK_ORDER):
                label = hand_label(i, j)
                in_range = label in hand_set
                is_hl = label == highlight

                bg = color if in_range else "#f1f5f9"
                fg = "#ffffff" if in_range else "#94a3b8"
                outline = "#fbbf24" if is_hl else "#cbd5e1"
                lw = 2 if is_hl else 1

                self.create_rectangle(
                    ox + j * c, oy + i * c,
                    ox + (j + 1) * c, oy + (i + 1) * c,
                    fill=bg, outline=outline, width=lw,
                )
                self.create_text(ox + j * c + c / 2, oy + i * c + c / 2,
                                 text=label, fill=fg,
                                 font=("Segoe UI", cell_font_size))