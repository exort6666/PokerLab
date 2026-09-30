"""
Monte-Carlo DCFR для N-player префлоп-солвера (chipEV).

v5.1 (текущая):
    * `validate_2max` переписан: теперь тестирует ОБЕ модели на ПОЛНОМ
      дереве (с open/3bet/4bet), где реально существуют постфлоп-узлы.
    * Добавлен `compare_models`: один стек, два прогона, разные модели,
      полное дерево. Печатает сравнение диапазонов.
    * `validate_2max` (push/fold) вынесен в `validate_pushfold_2max`.

v5: параметр postflop_model ("allin_equivalent" | "equity_only").
v4: DCFR + explicit averaging.
v3: DCFR, strat_sum только для семплированной руки.
v2: strat_sum только для семплированной руки.
v1: strat_sum для всех рук (баг сходимости).

Reference:
    Brown & Sandholm (2019). Solving Imperfect-Information Games
    via Discounted Regret Minimization.
    Lanctot et al. (2009). Monte Carlo Sampling for Regret
    Minimization in Extensive Games.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable, Literal

import numpy as np

from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS
from pokerlab.mtt.preflop_tree import (
    PreflopNode, TreeConfig, ActionType,
    build_preflop_tree, iter_nodes, node_count,
)

log = logging.getLogger(__name__)


# ============================================================
# DCFR параметры
# ============================================================

DCFR_ALPHA = 1.5
DCFR_BETA = 0.0
DCFR_GAMMA = 2.0


PostflopModel = Literal["allin_equivalent", "equity_only"]


# ============================================================
# Колода
# ============================================================

_RANKS = "AKQJT98765432"
_SUITS = "shdc"
DECK = tuple(r + s for r in _RANKS for s in _SUITS)


def _canonical_hand(c1: str, c2: str) -> str:
    r1, s1 = c1[0], c1[1]
    r2, s2 = c2[0], c2[1]
    if _RANKS.index(r1) > _RANKS.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        return r1 + r2
    if s1 == s2:
        return r1 + r2 + "s"
    return r1 + r2 + "o"


def _default_evaluator(cards: list[str]) -> int:
    from phevaluator import evaluate_cards
    return evaluate_cards(*cards)


# ============================================================
# Результат
# ============================================================

@dataclass
class PreflopStrategyMC:
    strategies: dict[str, np.ndarray]
    actions_of: dict[str, list]
    node_meta: dict[str, dict]
    cfg: TreeConfig
    iterations: int
    elapsed_sec: float
    postflop_model: str = "allin_equivalent"


# ============================================================
# Solver
# ============================================================

class PreflopSolverMC:

    def __init__(
        self,
        cfg: TreeConfig,
        evaluator: Callable[[list[str]], int] | None = None,
        seed: int = 42,
        postflop_model: PostflopModel = "allin_equivalent",
    ):
        self.cfg = cfg
        self.positions = list(cfg.positions())
        self.root = build_preflop_tree(cfg)
        self.evaluate = evaluator or _default_evaluator
        self.rng = random.Random(seed)
        self.postflop_model = postflop_model

        self.hand_to_idx = {h: i for i, h in enumerate(ALL_HANDS)}

        self.regret: dict[str, np.ndarray] = {}
        self.strat_sum: dict[str, np.ndarray] = {}
        self.actions_of: dict[str, list] = {}

        for node in iter_nodes(self.root):
            if node.is_terminal:
                continue
            key = node.key()
            n = len(node.actions)
            self.regret[key] = np.zeros((N_HANDS, n), dtype=np.float64)
            self.strat_sum[key] = np.zeros((N_HANDS, n), dtype=np.float64)
            self.actions_of[key] = list(node.actions)

    def _current_strategy(self, key: str) -> np.ndarray:
        r = np.maximum(self.regret[key], 0.0)
        s = r.sum(axis=1, keepdims=True)
        n = r.shape[1]
        return np.where(s > 0, r / np.where(s > 0, s, 1.0), 1.0 / n)

    def _sample_deal(self):
        n = len(self.positions)
        cards = self.rng.sample(DECK, 2 * n + 5)
        hands = {}
        for i, p in enumerate(self.positions):
            hands[p] = [cards[2 * i], cards[2 * i + 1]]
        board = cards[2 * n:]
        return hands, board

    def _live_players(self, node: PreflopNode) -> list[str]:
        if node.fold_to_win:
            return [node.winner_if_fold] if node.winner_if_fold else []
        if not node.invested:
            return []
        max_inv = max(node.invested.values())
        return [p for p, inv in node.invested.items()
                if inv >= max_inv - 1e-6]

    def _terminal_utils(
        self,
        node: PreflopNode,
        hands: dict[str, list[str]],
        board: list[str],
    ) -> dict[str, float]:
        u = {p: 0.0 for p in self.positions}
        pot = float(node.pot_bb)
        inv = dict(node.invested)

        if node.fold_to_win:
            winner = node.winner_if_fold
            for p in self.positions:
                u[p] = (pot - inv[p]) if p == winner else -inv[p]
            return u

        if node.allin_showdown or node.goes_to_postflop:
            live = self._live_players(node)
            if not live:
                return u

            if node.goes_to_postflop:
                if self.postflop_model == "allin_equivalent":
                    S = self.cfg.stack_bb
                    final_pot = pot
                    final_inv = dict(inv)
                    for p in live:
                        extra = max(0.0, S - inv[p])
                        final_pot += extra
                        final_inv[p] = S
                else:
                    final_pot = pot
                    final_inv = dict(inv)
            else:
                final_pot = pot
                final_inv = dict(inv)

            ranks = {p: self.evaluate(hands[p] + board) for p in live}
            best = min(ranks.values())
            winners = [p for p, r in ranks.items() if r == best]
            share = final_pot / len(winners)

            for p in self.positions:
                u[p] = share - final_inv[p] if p in winners else -final_inv[p]
            return u

        raise ValueError(f"Неизвестный терминал: {node.key()}")

    def _traverse(
        self,
        node: PreflopNode,
        hands: dict[str, list[str]],
        board: list[str],
        t: int,
        alpha_discount: float,
        beta_discount: float,
    ) -> dict[str, float]:
        if node.is_terminal:
            return self._terminal_utils(node, hands, board)

        key = node.key()
        actor = node.actor
        actions = node.actions
        n_act = len(actions)

        code = _canonical_hand(*hands[actor])
        i_p = self.hand_to_idx[code]

        sigma = self._current_strategy(key)[i_p]

        u_actions: list[dict[str, float]] = []
        for action in actions:
            child = node.children[action.short()]
            u_actions.append(self._traverse(
                child, hands, board, t, alpha_discount, beta_discount,
            ))

        u_node: dict[str, float] = {}
        for p in self.positions:
            u_node[p] = sum(sigma[a] * u_actions[a][p]
                            for a in range(n_act))

        for a in range(n_act):
            delta = u_actions[a][actor] - u_node[actor]
            old = self.regret[key][i_p, a]
            new_undisc = old + delta
            if new_undisc > 0:
                self.regret[key][i_p, a] = old * alpha_discount + delta
            else:
                self.regret[key][i_p, a] = old * beta_discount + delta

        return u_node

    def solve(self, iterations: int = 100_000,
              log_every: int = 10_000) -> PreflopStrategyMC:
        log.info(
            "MC-DCFR (%s): %d итераций (%d-max, α=%.1f β=%.1f γ=%.1f)",
            self.postflop_model, iterations, self.cfg.n_players,
            DCFR_ALPHA, DCFR_BETA, DCFR_GAMMA,
        )
        t0 = time.time()

        for t in range(1, iterations + 1):
            hands, board = self._sample_deal()

            alpha_discount = (t ** DCFR_ALPHA) / (t ** DCFR_ALPHA + 1.0)
            beta_discount = (t ** DCFR_BETA) / (t ** DCFR_BETA + 1.0)

            self._traverse(
                self.root, hands, board, t,
                alpha_discount, beta_discount,
            )

            gamma_weight = ((t - 1.0) / t) ** DCFR_GAMMA if t > 1 else 0.0
            for key in self.regret:
                sigma_all = self._current_strategy(key)
                self.strat_sum[key] = (
                    self.strat_sum[key] * gamma_weight + sigma_all
                )

            if log_every and t % log_every == 0:
                elapsed = time.time() - t0
                rate = t / elapsed
                eta = (iterations - t) / rate if rate > 0 else 0
                log.info("  iter %d/%d | %.0f iter/s | ETA %.0f сек",
                         t, iterations, rate, eta)

        avg_strategies = {}
        for key, ss in self.strat_sum.items():
            s = ss.sum(axis=1, keepdims=True)
            n = ss.shape[1]
            avg_strategies[key] = np.where(
                s > 0, ss / np.where(s > 0, s, 1.0), 1.0 / n
            )

        node_meta = {}
        for node in iter_nodes(self.root):
            node_meta[node.key()] = {
                "actor": node.actor,
                "pot_bb": node.pot_bb,
                "invested": dict(node.invested),
                "is_terminal": node.is_terminal,
                "fold_to_win": node.fold_to_win,
                "allin_showdown": node.allin_showdown,
                "goes_to_postflop": node.goes_to_postflop,
                "winner_if_fold": node.winner_if_fold,
                "history": list(node.history),
            }

        elapsed = time.time() - t0
        log.info("Готово за %.1f сек (%.1f мин)", elapsed, elapsed / 60)

        return PreflopStrategyMC(
            strategies=avg_strategies,
            actions_of=self.actions_of,
            node_meta=node_meta,
            cfg=self.cfg,
            iterations=iterations,
            elapsed_sec=elapsed,
            postflop_model=self.postflop_model,
        )


# ============================================================
# Утилиты
# ============================================================

def print_root_summary(res: PreflopStrategyMC, top_n: int = 15) -> None:
    key = "ROOT"
    if key not in res.strategies:
        print("Нет ROOT")
        return
    sigma = res.strategies[key]
    actions = res.actions_of[key]
    actor = res.node_meta[key]["actor"]
    print(f"--- ROOT (actor={actor}, "
          f"actions={[a.short() for a in actions]}) ---")
    print(f"{'Hand':>6} | " + " ".join(f"{a.short():>8}" for a in actions))
    for i in range(min(top_n, N_HANDS)):
        row = " ".join(f"{sigma[i, a]:8.3f}" for a in range(len(actions)))
        print(f"{ALL_HANDS[i]:>6} | {row}")


def range_pct(hands: list[str]) -> float:
    from pokerlab.mtt.cfr_pushfold import COMBOS
    total = sum(COMBOS[ALL_HANDS.index(h)] for h in hands)
    return total / 1326.0 * 100


def _dom_action(sigma_row: np.ndarray) -> int:
    """Индекс доминирующего действия."""
    return int(np.argmax(sigma_row))


def _action_summary(res: PreflopStrategyMC, key: str) -> dict:
    """Сколько рук доминирует в каждом действии узла."""
    if key not in res.strategies:
        return {}
    sigma = res.strategies[key]
    actions = res.actions_of[key]
    n_act = len(actions)
    counts = {a.short(): 0 for a in actions}
    for i in range(N_HANDS):
        dom = _dom_action(sigma[i])
        counts[actions[dom].short()] += 1
    return counts


# ============================================================
# Тесты
# ============================================================

def validate_pushfold_2max(stack: float = 10.0,
                           iterations: int = 50_000) -> None:
    """
    Чистый push/fold (открытия отключены). Валидирует ядро CFR.
    Для сравнения моделей — НЕ использовать (нет постфлоп-узлов).
    """
    cfg = TreeConfig(
        n_players=2, stack_bb=stack, ante_bb=0.0,
        open_size=stack + 100,
        three_bet_size=stack + 100,
        four_bet_size=stack + 100,
    )
    solver = PreflopSolverMC(cfg, seed=42)
    res = solver.solve(iterations=iterations, log_every=0)

    sigma = res.strategies["ROOT"]
    actions = res.actions_of["ROOT"]
    idx_push = next(i for i, a in enumerate(actions)
                    if a.type == ActionType.ALLIN)

    push_hands = [ALL_HANDS[i] for i in range(N_HANDS)
                  if sigma[i, idx_push] > 0.5]
    print(f"[push/fold validate, {stack} BB] "
          f"push {len(push_hands)} рук ({range_pct(push_hands):.1f}%)")
    for h in ("AA", "KK", "QQ", "AKs", "AKo", "72o"):
        i = ALL_HANDS.index(h)
        print(f"  {h}: push={sigma[i, idx_push]:.3f}")


def compare_models(stack: float = 30.0,
                   iterations: int = 100_000,
                   n_players: int = 2) -> None:
    """
    Сравнение моделей на ПОЛНОМ дереве (с open/3bet/4bet).

    Это правильный тест: узлы `goes_to_postflop` существуют,
    и postflop_model реально влияет на результат.
    """
    print(f"=== Сравнение моделей на {stack} BB ({n_players}-max) ===")
    print(f"    iterations = {iterations}")
    print()

    results: dict[str, PreflopStrategyMC] = {}

    for model in ("allin_equivalent", "equity_only"):
        cfg = TreeConfig(n_players=n_players, stack_bb=stack, ante_bb=0.0)
        solver = PreflopSolverMC(cfg, seed=42, postflop_model=model)
        n_nodes = node_count(solver.root)
        n_postflop = sum(1 for nd in iter_nodes(solver.root)
                         if nd.goes_to_postflop)
        print(f"--- {model} | дерево: {n_nodes} узлов, "
              f"postflop-терминалов: {n_postflop} ---")
        res = solver.solve(iterations=iterations, log_every=0)
        results[model] = res
        print()

    # --- Сравнение ROOT ---
    print("=== ROOT сравнение ===")
    r_a = results["allin_equivalent"]
    r_b = results["equity_only"]
    actions = r_a.actions_of["ROOT"]

    print(f"Действия ROOT: {[a.short() for a in actions]}")
    print()

    counts_a = _action_summary(r_a, "ROOT")
    counts_b = _action_summary(r_b, "ROOT")
    print(f"{'Action':>10} | {'allin_equiv':>12} | {'equity_only':>12} | delta")
    for a in actions:
        s = a.short()
        print(f"{s:>10} | {counts_a.get(s, 0):>12} | "
              f"{counts_b.get(s, 0):>12} | "
              f"{counts_b.get(s, 0) - counts_a.get(s, 0):+d}")

    # Ключевые руки
    print()
    print("=== Ключевые руки на ROOT ===")
    sigma_a = r_a.strategies["ROOT"]
    sigma_b = r_b.strategies["ROOT"]
    header = " ".join(f"{a.short():>14}" for a in actions)
    print(f"{'Hand':>6} | {header}")
    for h in ("AA", "KK", "QQ", "AKs", "AKo", "AQs", "T9s", "72o"):
        i = ALL_HANDS.index(h)
        row_a = " ".join(f"{sigma_a[i, x]:.3f}/{sigma_b[i, x]:.3f}".rjust(14)
                         for x in range(len(actions)))
        print(f"{h:>6} | {row_a}")

    # Также — стандартный summary
    print()
    print("--- allin_equivalent ---")
    print_root_summary(r_a, top_n=10)
    print()
    print("--- equity_only ---")
    print_root_summary(r_b, top_n=10)


def demo_3max(stack: float = 20.0,
              iterations: int = 30_000,
              postflop_model: PostflopModel = "allin_equivalent") -> None:
    cfg = TreeConfig(n_players=3, stack_bb=stack, ante_bb=0.0)
    solver = PreflopSolverMC(cfg, seed=42, postflop_model=postflop_model)
    print(f"3-max дерево: {node_count(solver.root)} узлов, "
          f"модель: {postflop_model}")
    res = solver.solve(iterations=iterations, log_every=5_000)
    print()
    print_root_summary(res, top_n=10)


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        validate_pushfold_2max(stack=10.0, iterations=50_000)
        validate_pushfold_2max(stack=20.0, iterations=50_000)
    elif len(sys.argv) > 2 and sys.argv[1] == "compare":
        stack = float(sys.argv[2])
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        compare_models(stack=stack, iterations=100_000, n_players=n)
    else:
        demo_3max(stack=20.0, iterations=30_000)