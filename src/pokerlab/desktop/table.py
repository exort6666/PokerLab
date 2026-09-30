"""Canvas с покерным столом (адаптивный)."""

from __future__ import annotations

import math
import tkinter as tk

from pokerlab.desktop.constants import (
    ACTIVE_BG, CALLER_BG, CARD_BG, CHIP_EDGE, CHIP_FILL,
    CURRENT_ACTOR_BORDER, FOLDED_BG, HERO_BG, PANEL, PUSHER_BG,
    SUIT_COLORS, SUIT_SYMBOLS, TABLE_EDGE, TABLE_FELT, TEXT,
)
from pokerlab.desktop.utils import format_action, parse_cards


PLAYER_W = 150
PLAYER_H = 130


class PokerTableCanvas(tk.Canvas):

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=PANEL, highlightthickness=0, **kwargs)
        self.hand_data = None
        self.current_action_idx = -1
        self.pusher_name = ""
        self.caller_name = ""
        # Перерисовка при изменении размера
        self.bind("<Configure>", lambda e: self.render())

    def set_hand(self, hand_data, pusher: str, caller: str) -> None:
        self.hand_data = hand_data
        self.pusher_name = pusher
        self.caller_name = caller
        self.current_action_idx = -1
        self.render()

    def step(self, idx: int) -> None:
        self.current_action_idx = idx
        self.render()

    def total_steps(self) -> int:
        if not self.hand_data:
            return 0
        n = len(self.hand_data["actions"])
        return n + self._extra_board_steps()

    # --- Логика ---

    def _is_allin_preflop(self) -> bool:
        if not self.hand_data:
            return False
        actions = self.hand_data["actions"]
        has_postflop = any(
            a["street"] in ("flop", "turn", "river") for a in actions
        )
        if has_postflop:
            return False
        board_total = len(self.hand_data["hand"]["board"] or "") // 2
        return board_total >= 3

    def _extra_board_steps(self) -> int:
        if not self._is_allin_preflop():
            return 0
        board_total = len(self.hand_data["hand"]["board"] or "") // 2
        if board_total == 5:
            return 3
        if board_total == 4:
            return 2
        if board_total == 3:
            return 1
        return 0

    def _board_count(self) -> int:
        if self.current_action_idx < 0 or not self.hand_data:
            return 0
        actions = self.hand_data["actions"]
        n = len(actions)
        idx = self.current_action_idx
        board_total = len(self.hand_data["hand"]["board"] or "") // 2
        if idx < n:
            s = actions[idx]["street"]
            if s == "flop":
                return min(3, board_total)
            if s == "turn":
                return min(4, board_total)
            if s == "river":
                return min(5, board_total)
            return 0
        extra = idx - n
        return min(3 + extra, board_total)

    def _reveal_cards(self, player_name: str) -> bool:
        if not self.hand_data:
            return False
        if player_name == "Hero":
            return True
        if self.current_action_idx < self.total_steps() - 1:
            return False
        for p in self.hand_data["players"]:
            if p["name"] == player_name:
                return bool(p.get("cards"))
        return False

    # --- Рендер ---

    def render(self) -> None:
        self.delete("all")
        if not self.hand_data:
            return

        hand = self.hand_data["hand"]
        players = self.hand_data["players"]
        actions = self.hand_data["actions"]
        bb = hand["bb"]
        n = len(actions)

        # Адаптивный размер
        w = self.winfo_width() or 900
        h = self.winfo_height() or 620
        if w < 100:
            w = 900
        if h < 100:
            h = 620

        cx, cy = w // 2, h // 2

        # Овал максимально крупный, но с учётом боксов игроков:
        # бокс 150×130, значит по горизонтали нужно ~75 px запаса,
        # по вертикали ~65 px.
        rx = max(200, min(int(w * 0.44), 480, w // 2 - 80))
        ry = max(150, min(int(h * 0.40), 280, h // 2 - 80))

        # Овалы
        self.create_oval(
            cx - rx, cy - ry, cx + rx, cy + ry,
            fill=TABLE_FELT, outline=TABLE_EDGE, width=6,
        )
        self.create_oval(
            cx - rx + 40, cy - ry + 30, cx + rx - 40, cy + ry - 30,
            outline="#4ade80", width=1, dash=(4, 4),
        )

        # POT и ANTE над борд-картами
        pot = 0
        ante_total = 0
        if self.current_action_idx >= 0:
            if self.current_action_idx < n:
                pot = actions[self.current_action_idx].get("pot_after") or 0
            else:
                pot = actions[-1].get("pot_after") or 0
            for a in actions[: min(self.current_action_idx + 1, n)]:
                if a["action"] in ("post_ante", "post_ante_all"):
                    ante_total += a.get("amount") or 0

        pot_bb = pot / bb if bb else 0
        ante_bb = ante_total / bb if bb else 0

        if ante_total > 0:
            self.create_text(
                cx, cy - 62,
                text=f"ANTE: {ante_bb:.2f} BB",
                fill="#fbbf24", font=("Segoe UI", 11, "bold"),
            )

        self.create_text(
            cx, cy - 38,
            text=f"POT: {pot_bb:.1f} BB",
            fill="#ffffff", font=("Segoe UI", 15, "bold"),
        )

        # Борд
        self._draw_board(cx, cy + 20, hand.get("board") or "",
                         self._board_count())

        # Состояние
        folded: set = set()
        all_in: set = set()
        contributed: dict = {}
        last_actor = None
        last_actions_by_player: dict = {}

        if self.current_action_idx >= 0:
            for a in actions[: min(self.current_action_idx + 1, n)]:
                name = a["player_name"]
                if a["action"] == "fold":
                    folded.add(name)
                if a["is_all_in"]:
                    all_in.add(name)
                if a["action"] in ("post_sb", "post_bb",
                                   "call", "bet", "raise"):
                    contributed[name] = (
                        contributed.get(name, 0) + (a["amount"] or 0)
                    )
                last_actions_by_player[name] = format_action(a)
            if self.current_action_idx < n:
                last_actor = actions[self.current_action_idx]["player_name"]
                if actions[self.current_action_idx]["action"] == "post_ante_all":
                    last_actor = None

        # Позиции
        positions: dict = {}
        n_players = len(players)
        for i, p in enumerate(players):
            angle = -90 + i * (360 / n_players)
            rad = math.radians(angle)
            px = cx + rx * math.cos(rad)
            py = cy + ry * math.sin(rad)
            positions[p["name"]] = (px, py, p)

        # Сначала прямоугольники
        for name, (px, py, p) in positions.items():
            self._draw_player_box(
                px, py, p, bb, folded, all_in, contributed,
                last_actor, last_actions_by_player,
            )

        # Затем плашки
        for name, (px, py, p) in positions.items():
            invested = contributed.get(name, 0)
            if invested > 0:
                self._draw_bet_chip(px, py, cx, cy, invested, bb)

        # Линии для текущего актёра
        for name, (px, py, p) in positions.items():
            if name == last_actor:
                self.create_line(
                    px, py, cx, cy, fill=CURRENT_ACTOR_BORDER,
                    width=2, dash=(3, 3),
                )

    def _draw_board(self, cx, cy, board_str, visible):
        cw, ch = 44, 60
        gap = 6
        total = 5 * cw + 4 * gap
        start_x = cx - total / 2
        cards = [
            (board_str[i], board_str[i + 1])
            for i in range(0, len(board_str), 2)
        ]
        for i in range(5):
            x = start_x + i * (cw + gap)
            y = cy
            if i < visible and i < len(cards):
                rank, suit = cards[i]
                self.create_rectangle(
                    x, y - ch / 2, x + cw, y + ch / 2,
                    fill=CARD_BG, outline="#1e293b", width=2,
                )
                color = SUIT_COLORS.get(suit, "#000")
                self.create_text(x + cw / 2, y - 11, text=rank,
                                 fill=color, font=("Segoe UI", 16, "bold"))
                self.create_text(x + cw / 2, y + 12,
                                 text=SUIT_SYMBOLS.get(suit, suit),
                                 fill=color, font=("Segoe UI", 16, "bold"))
            else:
                self.create_rectangle(
                    x, y - ch / 2, x + cw, y + ch / 2,
                    fill="#1b4332", outline="#4ade80",
                    width=1, dash=(3, 3),
                )

    def _draw_player_box(self, x, y, p, bb, folded, all_in, contributed,
                         last_actor, last_actions):
        w, h = PLAYER_W, PLAYER_H
        name = p["name"]
        is_hero = bool(p.get("is_hero"))
        is_pusher = name == self.pusher_name
        is_caller = name == self.caller_name
        is_folded = name in folded
        is_all_in = name in all_in
        is_current = name == last_actor

        if is_folded:
            bg = FOLDED_BG
        elif is_hero:
            bg = HERO_BG
        elif is_pusher:
            bg = PUSHER_BG
        elif is_caller:
            bg = CALLER_BG
        else:
            bg = ACTIVE_BG

        fg = "#ffffff" if bg in (HERO_BG, PUSHER_BG, CALLER_BG) else TEXT
        if is_folded:
            fg = "#64748b"

        outline = CURRENT_ACTOR_BORDER if is_current else "#1e293b"
        lw = 4 if is_current else 2

        self.create_rectangle(
            x - w / 2, y - h / 2, x + w / 2, y + h / 2,
            fill=bg, outline=outline, width=lw,
        )

        short_name = name if len(name) <= 10 else name[:9] + "…"
        self.create_text(x, y - h / 2 + 14,
                         text=f"S{p['seat']} {short_name}",
                         fill=fg, font=("Segoe UI", 9, "bold"))
        self.create_text(x, y - h / 2 + 30,
                         text=p.get("position") or "—",
                         fill=fg, font=("Segoe UI", 10, "bold"))

        stack = p.get("stack_start", 0)
        invested = contributed.get(name, 0)
        remaining = max(0, stack - invested)
        stack_bb = remaining / bb if bb else 0
        self.create_text(x, y - h / 2 + 48, text=f"{stack_bb:.1f} BB",
                         fill=fg, font=("Segoe UI", 10))

        status = ""
        status_color = fg
        if is_folded:
            status = "FOLD"
            status_color = "#94a3b8"
        elif is_all_in:
            status = "ALL-IN"
            status_color = "#dc2626"
        elif is_current:
            status = "▸ действует"
            status_color = "#f59e0b"

        last_act = last_actions.get(name, "")
        if last_act:
            self.create_text(x, y - h / 2 + 68, text=last_act,
                             fill="#0f172a", font=("Segoe UI", 9, "bold"))
        elif status:
            self.create_text(x, y - h / 2 + 68, text=status,
                             fill=status_color,
                             font=("Segoe UI", 9, "bold"))

        if p.get("cards") and self._reveal_cards(name):
            cards = parse_cards(p["cards"])
            cw, ch = 34, 46
            gap = 4
            n_cards = len(cards)
            total_w = n_cards * cw + (n_cards - 1) * gap
            start_x = x - total_w / 2
            card_y = y + h / 2 - 26
            for i, (rank, suit) in enumerate(cards):
                ccx = start_x + i * (cw + gap)
                bg_card = "#f1f5f9" if is_folded else CARD_BG
                self.create_rectangle(
                    ccx, card_y - ch / 2, ccx + cw, card_y + ch / 2,
                    fill=bg_card, outline="#1e293b", width=1.5,
                )
                color = SUIT_COLORS.get(suit, "#000")
                if is_folded:
                    color = "#94a3b8"
                self.create_text(ccx + cw / 2, card_y - 9, text=rank,
                                 fill=color, font=("Segoe UI", 13, "bold"))
                self.create_text(ccx + cw / 2, card_y + 11,
                                 text=SUIT_SYMBOLS.get(suit, suit),
                                 fill=color, font=("Segoe UI", 13, "bold"))

    def _draw_bet_chip(self, px, py, cx, cy, invested, bb):
        invested_bb = invested / bb if bb else 0
        label = f"{invested_bb:.1f} BB"
        t = 0.42
        chip_x = px + (cx - px) * t
        chip_y = py + (cy - py) * t

        self.create_oval(
            chip_x - 32, chip_y - 14,
            chip_x + 32, chip_y + 14,
            fill=CHIP_FILL, outline=CHIP_EDGE, width=2,
        )
        self.create_text(chip_x, chip_y, text=label,
                         fill="#ffffff",
                         font=("Segoe UI", 10, "bold"))