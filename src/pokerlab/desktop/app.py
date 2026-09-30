"""Главное окно ReviewApp."""

from __future__ import annotations

import json
import tkinter as tk
from tkinter import messagebox, ttk

from pokerlab.desktop.constants import BG, PANEL, TEXT, WIN_H, WIN_W
from pokerlab.desktop.data import (
    delete_bounty,
    load_hand_full,
    load_tournaments_with_hands,
    save_bounty,
)
from pokerlab.desktop.range_widget import RangeCanvas
from pokerlab.desktop.table import PokerTableCanvas
from pokerlab.desktop.utils import compress_actions, format_action
from pokerlab.mtt.hu_solver import solve_hu_chipEV


def format_date(iso: str | None) -> str:
    if not iso:
        return "—"
    return iso[:10]


def format_money(cents: int | None) -> str:
    if cents is None:
        return "—"
    return f"${cents / 100:.2f}"


def tournament_tag(tour: dict) -> str:
    name = (tour["tournament_name"] or "").lower()
    if tour["is_bounty"]:
        return "tour_bounty"
    if "turbo" in name or "hyper" in name:
        return "tour_turbo"
    return "tour_regular"


def _fmt_ev_bb(ev: float | None) -> str:
    """EV действия Hero в BB: '+2.82 BB' / '-1.17 BB' / '—'."""
    if ev is None:
        return "—"
    return f"{ev:+.2f} BB"


class ReviewApp:

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("PokerLab — HU Review")

        try:
            self.root.state("zoomed")
        except tk.TclError:
            self.root.geometry(
                f"{self.root.winfo_screenwidth()}x"
                f"{self.root.winfo_screenheight()}+0+0"
            )
        self.root.update_idletasks()

        self.root.configure(bg=BG)

        self.tournaments = load_tournaments_with_hands()
        self.show_errors_only = tk.BooleanVar(value=True)

        self.current_hand_data = None
        self.current_hand_id = None
        self.current_tournament_hands: list = []
        self.current_hand_index = -1
        self.details = {}
        self.action_idx = -1
        self.pusher_name = ""
        self.caller_name = ""

        self._build_ui()
        self._populate_tree()

    # --- UI ---

    def _build_ui(self) -> None:
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=0, minsize=300)
        self.root.grid_columnconfigure(1, weight=1)

        self._build_left_panel()
        self._build_right_panel()

        self.root.bind("<Left>", lambda e: self._step_back())
        self.root.bind("<Right>", lambda e: self._step_fwd())
        self.root.bind("<Home>", lambda e: self._to_start())
        self.root.bind("<End>", lambda e: self._to_end())
        self.root.bind("<Escape>", lambda e: self.root.state("normal"))

    def _build_left_panel(self) -> None:
        left = tk.Frame(self.root, bg=PANEL, width=300)
        left.grid(row=0, column=0, sticky="nsw")
        left.grid_propagate(False)

        tk.Label(left, text="Турниры", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 13, "bold")).pack(pady=(10, 4))

        tk.Checkbutton(
            left, text="Только турниры с ошибками",
            variable=self.show_errors_only,
            bg=PANEL, fg=TEXT, selectcolor=PANEL, activebackground=PANEL,
            command=self._populate_tree, font=("Segoe UI", 10),
        ).pack(pady=(0, 6))

        legend = tk.Frame(left, bg=PANEL)
        legend.pack(fill="x", padx=6, pady=(0, 6))
        tk.Label(legend, text="● Bounty", fg="#e65100", bg=PANEL,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        tk.Label(legend, text="● Turbo", fg="#0d47a1", bg=PANEL,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)
        tk.Label(legend, text="● Reg", fg="#475569", bg=PANEL,
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=4)

        tree_frame = tk.Frame(left, bg=PANEL)
        tree_frame.pack(fill="both", expand=True, padx=2, pady=(0, 2))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "Tour.Treeview",
            background="#ffffff", fieldbackground="#ffffff",
            foreground=TEXT, font=("Segoe UI", 10), rowheight=26,
            borderwidth=0,
        )
        style.configure(
            "Tour.Treeview.Heading",
            background="#e2e8f0", foreground="#0f172a",
            font=("Segoe UI", 10, "bold"), relief="flat",
        )
        style.map(
            "Tour.Treeview",
            background=[("selected", "#10b981")],
            foreground=[("selected", "#ffffff")],
        )
        style.map(
            "Tour.Treeview.Heading",
            background=[("active", "#cbd5e1")],
        )

        sb = tk.Scrollbar(tree_frame)
        sb.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            tree_frame,
            columns=("info",),
            show="tree headings",
            style="Tour.Treeview",
            yscrollcommand=sb.set,
        )
        self.tree.heading("#0", text="Раздача")
        self.tree.heading("info", text="EV действия, BB")
        self.tree.column("#0", width=200, minwidth=150, stretch=True)
        self.tree.column("info", width=110, anchor="center", stretch=False)

        self.tree.pack(side="left", fill="both", expand=True)
        sb.config(command=self.tree.yview)

        self.tree.tag_configure(
            "tour_bounty",
            background="#ffe0b2", foreground="#bf360c",
            font=("Segoe UI", 10, "bold"),
        )
        self.tree.tag_configure(
            "tour_turbo",
            background="#bbdefb", foreground="#0d47a1",
            font=("Segoe UI", 10, "bold"),
        )
        self.tree.tag_configure(
            "tour_regular",
            background="#e2e8f0", foreground="#0f172a",
            font=("Segoe UI", 10, "bold"),
        )
        self.tree.tag_configure(
            "hand_ok",
            background="#ffffff", foreground="#059669",
            font=("Segoe UI", 10),
        )
        self.tree.tag_configure(
            "hand_bad",
            background="#ffffff", foreground="#dc2626",
            font=("Segoe UI", 10),
        )

        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.bind("<Double-1>", self._on_tree_double_click)

    def _build_right_panel(self) -> None:
        right = tk.Frame(self.root, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.grid_rowconfigure(0, weight=0)
        right.grid_rowconfigure(1, weight=1)
        right.grid_rowconfigure(2, weight=0)
        right.grid_columnconfigure(0, weight=1)

        top = tk.Frame(right, bg=BG)
        top.grid(row=0, column=0, sticky="ew")

        self.header_frame = tk.Frame(top, bg=PANEL,
                                     highlightthickness=1,
                                     highlightbackground="#e2e8f0")
        self.header_frame.pack(fill="x", padx=2, pady=(2, 2))

        self.hand_title = tk.Label(
            self.header_frame, text="Выбери раздачу слева",
            bg=PANEL, fg=TEXT,
            font=("Segoe UI", 14, "bold"), anchor="w",
        )
        self.hand_title.pack(fill="x", padx=12, pady=(6, 0))

        self.tournament_label = tk.Label(
            self.header_frame, text="", bg=PANEL, fg="#64748b",
            font=("Segoe UI", 10), anchor="w",
        )
        self.tournament_label.pack(fill="x", padx=12, pady=(2, 6))

        self.metrics_frame = tk.Frame(top, bg=BG)
        self.metrics_frame.pack(fill="x", padx=2, pady=(0, 2))

        self.bounty_panel = tk.Frame(top, bg=PANEL,
                                     highlightthickness=1,
                                     highlightbackground="#e2e8f0")
        self.bounty_panel.pack(fill="x", padx=2, pady=(0, 2))
        self._build_bounty_content(self.bounty_panel)

        content = tk.Frame(right, bg=BG)
        content.grid(row=1, column=0, sticky="nsew", padx=2, pady=(0, 2))
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=0)

        table_wrapper = tk.Frame(content, bg=PANEL, highlightthickness=1,
                                 highlightbackground="#e2e8f0")
        table_wrapper.grid(row=0, column=0, sticky="nsew")

        self.poker_table = PokerTableCanvas(table_wrapper)
        self.poker_table.pack(fill="both", expand=True, padx=2, pady=2)

        ranges_frame = tk.Frame(content, bg=BG)
        ranges_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 0))
        ranges_frame.grid_rowconfigure(0, weight=1)
        ranges_frame.grid_rowconfigure(1, weight=1)
        ranges_frame.grid_columnconfigure(0, weight=1)

        self.push_canvas = RangeCanvas(ranges_frame, "Push range (Pusher)")
        self.push_canvas.grid(row=0, column=0, sticky="nsew", pady=(0, 2))

        self.call_canvas = RangeCanvas(ranges_frame, "Call range (Caller)")
        self.call_canvas.grid(row=1, column=0, sticky="nsew")

        self._build_nav(right)

    def _build_bounty_content(self, panel: tk.Frame) -> None:
        self.bounty_header = tk.Label(
            panel, text="Баунти (ручной ввод, $)",
            bg=PANEL, fg="#64748b",
            font=("Segoe UI", 9, "bold"),
        )
        self.bounty_header.pack(anchor="w", padx=12, pady=(8, 4))

        self.bounty_fields_frame = tk.Frame(panel, bg=PANEL)
        self.bounty_fields_frame.pack(fill="x", padx=12, pady=(0, 8))

        tk.Label(self.bounty_fields_frame, text="Hero:", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10)).pack(side="left", padx=(0, 4))

        self.hero_bounty_var = tk.StringVar(value="")
        tk.Entry(self.bounty_fields_frame, textvariable=self.hero_bounty_var,
                 width=10, font=("Consolas", 10)).pack(side="left",
                                                       padx=(0, 16))

        tk.Label(self.bounty_fields_frame, text="Оппонент:", bg=PANEL,
                 fg=TEXT, font=("Segoe UI", 10)).pack(side="left",
                                                      padx=(0, 4))

        self.villain_bounty_var = tk.StringVar(value="")
        tk.Entry(self.bounty_fields_frame, textvariable=self.villain_bounty_var,
                 width=10, font=("Consolas", 10)).pack(side="left",
                                                       padx=(0, 16))

        btn_style = {
            "bg": "#10b981", "fg": "#ffffff",
            "font": ("Segoe UI", 10, "bold"),
            "border": 0, "padx": 14, "pady": 4,
            "activebackground": "#059669",
            "activeforeground": "#ffffff",
            "cursor": "hand2",
        }
        self.save_btn = tk.Button(
            self.bounty_fields_frame, text="Сохранить",
            command=self._save_bounty, **btn_style,
        )
        self.save_btn.pack(side="left", padx=4)

        clear_style = dict(btn_style)
        clear_style["bg"] = "#94a3b8"
        clear_style["activebackground"] = "#64748b"
        self.clear_btn = tk.Button(
            self.bounty_fields_frame, text="Очистить",
            command=self._clear_bounty, **clear_style,
        )
        self.clear_btn.pack(side="left", padx=4)

        self.start_bounty_label = tk.Label(
            panel, text="", bg=PANEL, fg="#94a3b8",
            font=("Segoe UI", 9, "italic"),
        )
        self.start_bounty_label.pack(anchor="w", padx=12, pady=(0, 8))

        self.not_bounty_label = tk.Label(
            panel,
            text="Не bounty-турнир — баунти отсутствует у всех игроков",
            bg=PANEL, fg="#94a3b8",
            font=("Segoe UI", 10, "italic"),
        )

    def _build_nav(self, parent: tk.Frame) -> None:
        nav = tk.Frame(parent, bg=PANEL, highlightthickness=1,
                       highlightbackground="#e2e8f0")
        nav.grid(row=2, column=0, sticky="ew", pady=(0, 2))

        btn_style = {
            "bg": "#10b981", "fg": "#ffffff",
            "font": ("Segoe UI", 11, "bold"),
            "border": 0, "padx": 20, "pady": 8,
            "activebackground": "#059669",
            "activeforeground": "#ffffff",
            "cursor": "hand2",
        }
        nav_inner = tk.Frame(nav, bg=PANEL)
        nav_inner.pack(pady=8)

        for text, cmd in [
            ("⏮ Начало", self._to_start),
            ("◀ Назад", self._step_back),
            ("Вперёд ▶", self._step_fwd),
            ("Конец ⏭", self._to_end),
        ]:
            tk.Button(nav_inner, text=text, command=cmd, **btn_style).pack(
                side="left", padx=4,
            )

        self.action_label = tk.Label(nav, text="—", bg=PANEL, fg=TEXT,
                                     font=("Consolas", 11), padx=10, pady=6)
        self.action_label.pack(fill="x")

    # --- Дерево ---

    def _populate_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())

        for tour in self.tournaments:
            errs = tour["errors_count"]
            total = tour["hands_count"]

            if self.show_errors_only.get() and errs == 0:
                continue

            date = format_date(tour["tournament_date"])
            tag = tournament_tag(tour)

            if tour["is_bounty"]:
                type_marker = "★ BOUNTY"
            else:
                name_low = (tour["tournament_name"] or "").lower()
                if "turbo" in name_low or "hyper" in name_low:
                    type_marker = "⚡ TURBO"
                else:
                    type_marker = "◇ REG"

            err_marker = f"  🔴 {errs}" if errs > 0 else ""
            label = f"{type_marker}  {tour['tournament_name']}"
            info = f"{errs} ✗ / {total}"

            tour_node = self.tree.insert(
                "", "end",
                iid=f"t{tour['tournament_id']}",
                text=f"{label}  ({date}){err_marker}",
                values=(info,),
                tags=(tag,),
                open=False,
            )

            for h in tour["hands"]:
                marker = "✗" if not h["is_correct"] else "✓"
                h_tag = "hand_bad" if not h["is_correct"] else "hand_ok"

                details = {}
                if h.get("details"):
                    try:
                        details = json.loads(h["details"])
                    except (TypeError, ValueError):
                        details = {}
                hero_code = details.get("hero_code", "??")

                hero_pos = h.get("hero_position") or "?"
                hero_action = h.get("hero_action") or "?"

                # Основная строка: маркер + карты + позиция + действие
                main_text = (
                    f"   {marker}  {hero_code}  {hero_pos}  {hero_action}"
                )
                # Правая колонка: EV фактического действия Hero в BB
                info_val = _fmt_ev_bb(h.get("ev_actual"))

                self.tree.insert(
                    tour_node, "end",
                    iid=f"h{h['hand_id']}",
                    text=main_text,
                    values=(info_val,),
                    tags=(h_tag,),
                )

    def _on_tree_select(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("h"):
            hand_id = iid[1:]
            if hand_id == self.current_hand_id:
                return
            self._load_hand_by_id(hand_id)

    def _on_tree_double_click(self, _event) -> None:
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("t"):
            self.tree.item(iid, open=not self.tree.item(iid, "open"))

    def _load_hand_by_id(self, hand_id: str) -> None:
        for t in self.tournaments:
            for h_idx, h in enumerate(t["hands"]):
                if h["hand_id"] == hand_id:
                    self.current_tournament_hands = t["hands"]
                    self.current_hand_index = h_idx
                    self.current_hand_id = hand_id
                    self._load_hand(h)
                    return

    # --- Переход между раздачами ---

    def _next_hand(self) -> bool:
        if not self.current_tournament_hands:
            return False
        next_idx = self.current_hand_index + 1
        if next_idx >= len(self.current_tournament_hands):
            return False
        next_row = self.current_tournament_hands[next_idx]
        next_hand_id = next_row["hand_id"]
        self.current_hand_index = next_idx
        self.current_hand_id = next_hand_id
        self._load_hand(next_row)
        try:
            self.tree.selection_set(f"h{next_hand_id}")
            self.tree.see(f"h{next_hand_id}")
        except tk.TclError:
            pass
        return True

    def _prev_hand(self) -> bool:
        if not self.current_tournament_hands:
            return False
        prev_idx = self.current_hand_index - 1
        if prev_idx < 0:
            return False
        prev_row = self.current_tournament_hands[prev_idx]
        prev_hand_id = prev_row["hand_id"]
        self.current_hand_index = prev_idx
        self.current_hand_id = prev_hand_id
        self._load_hand(prev_row)
        try:
            self.tree.selection_set(f"h{prev_hand_id}")
            self.tree.see(f"h{prev_hand_id}")
        except tk.TclError:
            pass
        return True

    # --- Загрузка раздачи ---

    def _load_hand(self, row: dict) -> None:
        details = json.loads(row["details"]) if row["details"] else {}
        self.details = details
        data = load_hand_full(row["hand_id"])
        data["actions"] = compress_actions(data["actions"])
        self.current_hand_data = data

        self.pusher_name = ""
        self.caller_name = ""
        for p in data["players"]:
            if p["is_hero"]:
                if row["spot_type"] == "PREFLOP_HERO_PUSH":
                    self.pusher_name = p["name"]
                else:
                    self.caller_name = p["name"]
            else:
                if row["spot_type"] == "PREFLOP_HERO_PUSH":
                    self.caller_name = p["name"]
                else:
                    self.pusher_name = p["name"]

        hand = data["hand"]
        tour_name = hand.get("tournament_name") or "—"
        tour_date = format_date(hand.get("tournament_date"))
        buyin = format_money(hand.get("total_buyin_cents"))
        is_bounty = bool(hand.get("is_bounty"))

        verdict = "✓ Правильно" if row["is_correct"] else "✗ Ошибка"
        self.hand_title.config(
            text=f"{row['hand_id']}  |  {tour_name}  |  {verdict}",
            fg="#10b981" if row["is_correct"] else "#e74c3c",
        )
        self.tournament_label.config(
            text=f"Дата: {tour_date}   |   Бай-ин: {buyin}   |   "
                 f"Hero: {row['hero_action']} → надо: {row['optimal_action']}",
        )

        if is_bounty:
            self._show_bounty_panel(data)
        else:
            self._show_not_bounty_panel()

        self._render_metrics()
        self.poker_table.set_hand(data, self.pusher_name, self.caller_name)

        result = solve_hu_chipEV(
            pusher_start_bb=details.get("pusher_start_bb", 0),
            caller_start_bb=details.get("caller_start_bb", 0),
            pusher_inv_bb=details.get("pusher_inv_bb", 0),
            caller_inv_bb=details.get("caller_inv_bb", 0),
            dead_money_bb=details.get("dead_money_bb", 0),
            iterations=2000,
        )
        hero_code = details.get("hero_code")

        self.push_canvas.render(result.push_range, "#3498db",
                                highlight=hero_code, freq=result.push_freq)
        self.call_canvas.render(result.call_range, "#e74c3c",
                                highlight=hero_code, freq=result.call_freq)

        self.action_idx = -1
        self._update_nav()

    def _show_bounty_panel(self, data: dict) -> None:
        self.not_bounty_label.pack_forget()
        self.bounty_header.pack(anchor="w", padx=12, pady=(8, 4))
        self.bounty_fields_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.start_bounty_label.pack(anchor="w", padx=12, pady=(0, 8))

        bounty = data.get("bounty")
        if bounty:
            self.hero_bounty_var.set(f"{bounty['hero_bounty']:.2f}")
            self.villain_bounty_var.set(f"{bounty['villain_bounty']:.2f}")
        else:
            self.hero_bounty_var.set("")
            self.villain_bounty_var.set("")

        start_bounty_cents = data["hand"].get("start_bounty_cents") or 0
        self.start_bounty_label.config(
            text=f"Стартовое баунти турнира: {format_money(start_bounty_cents)}",
        )

    def _show_not_bounty_panel(self) -> None:
        self.bounty_header.pack_forget()
        self.bounty_fields_frame.pack_forget()
        self.start_bounty_label.pack_forget()
        self.not_bounty_label.pack(anchor="w", padx=12, pady=16)
        self.hero_bounty_var.set("0.00")
        self.villain_bounty_var.set("0.00")

    def _save_bounty(self) -> None:
        if not self.current_hand_id:
            return
        try:
            h = float(self.hero_bounty_var.get().strip() or 0)
            v = float(self.villain_bounty_var.get().strip() or 0)
        except ValueError:
            messagebox.showerror("Ошибка", "Введи числа, например 1.50")
            return
        try:
            save_bounty(self.current_hand_id, h, v)
        except ValueError as e:
            messagebox.showerror("Ошибка", str(e))
            return
        messagebox.showinfo("OK", f"Баунти сохранены: Hero ${h:.2f}, "
                                  f"Оппонент ${v:.2f}")

    def _clear_bounty(self) -> None:
        if not self.current_hand_id:
            return
        delete_bounty(self.current_hand_id)
        self.hero_bounty_var.set("")
        self.villain_bounty_var.set("")
        messagebox.showinfo("OK", "Баунти удалены")

    def _render_metrics(self) -> None:
        for w in self.metrics_frame.winfo_children():
            w.destroy()

        d = self.details
        eff = min(
            d.get("pusher_start_bb", 0) - d.get("pusher_inv_bb", 0),
            d.get("caller_start_bb", 0) - d.get("caller_inv_bb", 0),
        )
        metrics = [
            ("Карты", d.get("hero_code", "?")),
            ("Эффективный стек", f"{eff:.1f} BB"),
            ("Pusher", f"{d.get('pusher_start_bb', 0):.1f} BB"),
            ("Caller", f"{d.get('caller_start_bb', 0):.1f} BB"),
            ("Dead money", f"{d.get('dead_money_bb', 0):.1f} BB"),
        ]
        for label, value in metrics:
            f = tk.Frame(self.metrics_frame, bg=PANEL,
                         highlightthickness=1, highlightbackground="#e2e8f0")
            f.pack(side="left", expand=True, fill="both", padx=2)
            tk.Label(f, text=label, bg=PANEL, fg="#64748b",
                     font=("Segoe UI", 8, "bold")).pack(pady=(6, 0))
            tk.Label(f, text=value, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 12, "bold")).pack(pady=(0, 6))

    # --- Навигация ---

    def _total_steps(self) -> int:
        if not self.current_hand_data:
            return 0
        return self.poker_table.total_steps()

    def _step_fwd(self) -> None:
        if not self.current_hand_data:
            return
        if self.action_idx < self._total_steps() - 1:
            self.action_idx += 1
            self._update_nav()
        else:
            self._next_hand()

    def _step_back(self) -> None:
        if self.action_idx >= 0:
            self.action_idx -= 1
            self._update_nav()
        else:
            if self._prev_hand():
                self.action_idx = self._total_steps() - 1
                self._update_nav()

    def _to_start(self) -> None:
        self.action_idx = -1
        self._update_nav()

    def _to_end(self) -> None:
        if self.current_hand_data:
            self.action_idx = self._total_steps() - 1
            self._update_nav()

    def _update_nav(self) -> None:
        if not self.current_hand_data:
            return
        actions = self.current_hand_data["actions"]
        n = len(actions)
        total = self._total_steps()

        self.poker_table.step(self.action_idx)

        if self.action_idx < 0:
            self.action_label.config(
                text=f"⏮ 0/{total}  Перед первым действием  "
                     f"(← предыдущая раздача)",
                fg="#64748b",
            )
            return

        order = self.action_idx + 1
        if self.action_idx < n:
            a = actions[self.action_idx]
            self.action_label.config(
                text=f"[{order}/{total}]  {a['street'].upper()}  ▸  "
                     f"{a['player_name']}  ▸  {format_action(a)}",
                fg="#0f172a",
            )
        else:
            extra = self.action_idx - n
            labels = ["FLOP", "TURN", "RIVER"]
            label = labels[extra] if extra < len(labels) else "BOARD"
            self.action_label.config(
                text=f"[{order}/{total}]  BOARD  ▸  Открывается {label}",
                fg="#0f172a",
            )