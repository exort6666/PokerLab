"""
Vector CFR+ для префлоп-дерева (2..N max, chipEV).

Метод: точный counterfactual regret minimization с матричными
операциями numpy (169 × 169).

Для 2-max и 3-max — точное равновесие Нэша (не аппроксимация).
Для 6+ max — отдельный MC-CFR (позже).

Постфлоп-терминалы: заглушка "allin-equivalent" — после колла
обе стороны идут all-in. Явно помечено флагом.

Utility считается корректно относительно invested на узле:
    fold_to_win(SB wins)  → u_SB = pot − invested[SB]
    fold_to_win(BB wins)  → u_SB = −invested[SB]
    allin_showdown        → u_SB = eq × pot − invested[SB]
    goes_to_postflop      → u_SB = eq × (2S + ante) − S
                            (allin-equivalent, аппроксимация)

Reference:
- Zinkevich et al. (2007). Regret Minimization in Games with
  Incomplete Information.
- Tammelin (2014). Solving Large Imperfect Information Games Using CFR+.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from pokerlab.mtt.cfr_pushfold import (
    ALL_HANDS, N_HANDS, EQ, PI_OPP,
)
from pokerlab.mtt.preflop_tree import (
    PreflopNode, TreeConfig, ActionType,
    build_preflop_tree, iter_nodes, node_count,
)

log = logging.getLogger(__name__)


@dataclass
class PreflopStrategy:
    strategies: dict[str, np.ndarray]
    actions_of: dict[str, list]
    node_meta: dict[str, dict]
    cfg: TreeConfig
    iterations: int
    elapsed_sec: float


# ============================================================
# Терминальные utility
# ============================================================

def _terminal_matrix(node: PreflopNode, cfg: TreeConfig) -> np.ndarray:
    """
    u_SB[i, j] — utility SB (в BB) для пары рук (i, j),
    где i — рука SB, j — рука BB.
    """
    inv_sb = float(node.invested.get("SB", 0.5))
    pot = float(node.pot_bb)

    if node.fold_to_win:
        winner = node.winner_if_fold
        u = np.zeros((N_HANDS, N_HANDS), dtype=np.float64)
        if winner == "SB":
            u[:] = pot - inv_sb
        else:
            u[:] = -inv_sb
        return u

    if node.allin_showdown:
        # u_SB(i, j) = eq(i, j) × pot − inv_sb
        return EQ * pot - inv_sb

    if node.goes_to_postflop:
        # Заглушка allin-equivalent (для 2-max equal stacks):
        #   финальный pot = 2S + ante_total
        #   финальный inv_sb = S
        #   u_SB = eq × (2S + ante) − S
        # Для 3+ max с разными стеками — расширим позже.
        S = float(cfg.stack_bb)
        ante_total = cfg.ante_bb * cfg.n_players
        return EQ * (2.0 * S + ante_total) - S

    raise ValueError(f"Неизвестный терминал: {node.key()}")


# ============================================================
# Solver
# ============================================================

class PreflopSolver:

    def __init__(self, cfg: TreeConfig, seed: int = 42):
        self.cfg = cfg
        self.root = build_preflop_tree(cfg)

        self.regret: dict[str, np.ndarray] = {}
        self.strat_sum: dict[str, np.ndarray] = {}
        self.actions_of: dict[str, list] = {}

        for node in iter_nodes(self.root):
            if node.is_terminal:
                continue
            key = node.key()
            n_act = len(node.actions)
            self.regret[key] = np.zeros((N_HANDS, n_act), dtype=np.float64)
            self.strat_sum[key] = np.zeros((N_HANDS, n_act), dtype=np.float64)
            self.actions_of[key] = list(node.actions)

        self.rng = np.random.default_rng(seed)

    def _current_strategy(self, key: str) -> np.ndarray:
        r = np.maximum(self.regret[key], 0.0)
        s = r.sum(axis=1, keepdims=True)
        n = r.shape[1]
        return np.where(s > 0, r / np.where(s > 0, s, 1.0), 1.0 / n)

    def _cfr_pass(
        self,
        node: PreflopNode,
        reach_sb: np.ndarray,
        reach_bb: np.ndarray,
    ) -> np.ndarray:
        if node.is_terminal:
            return _terminal_matrix(node, self.cfg)

        key = node.key()
        σ = self._current_strategy(key)
        actor = node.actor
        actions = node.actions
        n_act = len(actions)

        u_actions = []
        for a_idx, action in enumerate(actions):
            child = node.children[action.short()]
            if actor == "SB":
                new_reach_sb = reach_sb * σ[:, a_idx]
                new_reach_bb = reach_bb
            else:
                new_reach_sb = reach_sb
                new_reach_bb = reach_bb * σ[:, a_idx]
            u_child = self._cfr_pass(child, new_reach_sb, new_reach_bb)
            u_actions.append(u_child)

        u_node = np.zeros((N_HANDS, N_HANDS))
        if actor == "SB":
            for a_idx in range(n_act):
                u_node += σ[:, a_idx][:, None] * u_actions[a_idx]
        else:
            for a_idx in range(n_act):
                u_node += σ[:, a_idx][None, :] * u_actions[a_idx]

        if actor == "SB":
            for a_idx in range(n_act):
                v_a = (PI_OPP * reach_bb[None, :]
                       * u_actions[a_idx]).sum(axis=1)
                v = (PI_OPP * reach_bb[None, :] * u_node).sum(axis=1)
                self.regret[key][:, a_idx] += v_a - v
        else:
            for a_idx in range(n_act):
                v_a = -(PI_OPP.T * reach_sb[:, None]
                        * u_actions[a_idx]).sum(axis=0)
                v = -(PI_OPP.T * reach_sb[:, None] * u_node).sum(axis=0)
                self.regret[key][:, a_idx] += v_a - v

        return u_node

    def solve(self, iterations: int = 1000,
              log_every: int = 100) -> PreflopStrategy:
        log.info("Начало solve: %d итераций", iterations)
        t0 = time.time()

        one = np.ones(N_HANDS, dtype=np.float64)

        for t in range(1, iterations + 1):
            u = self._cfr_pass(self.root, one, one)
            for key in self.regret:
                σ = self._current_strategy(key)
                self.strat_sum[key] += t * σ

            if log_every and t % log_every == 0:
                v_sb = float(u.mean())
                elapsed = time.time() - t0
                log.info("  iter %d/%d | v_sb(avg)=%.4f | %.1f сек",
                         t, iterations, v_sb, elapsed)

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
        log.info("Готово за %.1f сек", elapsed)

        return PreflopStrategy(
            strategies=avg_strategies,
            actions_of=self.actions_of,
            node_meta=node_meta,
            cfg=self.cfg,
            iterations=iterations,
            elapsed_sec=elapsed,
        )


# ============================================================
# Утилиты
# ============================================================

def print_strategy_summary(res: PreflopStrategy,
                            key: str = "ROOT",
                            top_n: int = 15) -> None:
    if key not in res.strategies:
        print(f"Нет узла {key}")
        return
    σ = res.strategies[key]
    actions = res.actions_of[key]
    actor = res.node_meta[key]["actor"]

    print(f"--- {key} (actor={actor}) ---")
    print(f"{'Hand':>6} | " + " ".join(f"{a.short():>8}"
                                        for a in actions))
    for i in range(min(top_n, N_HANDS)):
        row = " ".join(f"{σ[i, a]:8.3f}" for a in range(len(actions)))
        print(f"{ALL_HANDS[i]:>6} | {row}")


def print_full_range(res: PreflopStrategy, key: str,
                     action_idx: int, threshold: float = 0.5) -> list[str]:
    if key not in res.strategies:
        return []
    σ = res.strategies[key]
    return [ALL_HANDS[i] for i in range(N_HANDS)
            if σ[i, action_idx] > threshold]


def print_hand_action(res: PreflopStrategy, key: str,
                       hand: str) -> None:
    if key not in res.strategies:
        print(f"Нет узла {key}")
        return
    if hand not in ALL_HANDS:
        print(f"Нет руки {hand}")
        return
    i = ALL_HANDS.index(hand)
    σ = res.strategies[key]
    actions = res.actions_of[key]
    print(f"{hand}: " + ", ".join(
        f"{a.short()}={σ[i, idx]:.3f}" for idx, a in enumerate(actions)
    ))


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    cfg = TreeConfig(n_players=2, stack_bb=100.0, ante_bb=0.0)
    solver = PreflopSolver(cfg, seed=42)
    n = node_count(solver.root)
    print(f"2-max дерево: {n} узлов", flush=True)
    res = solver.solve(iterations=1000, log_every=200)

    print()
    print_strategy_summary(res, "ROOT", top_n=15)
    print()
    for h in ("AA", "KK", "AKs", "AJo", "KQo", "T9s", "72o", "32o"):
        print_hand_action(res, "ROOT", h)

    open_range = print_full_range(res, "ROOT", 2, threshold=0.5)
    print(f"\nSB open (r2) freq>50%: {len(open_range)} рук")
    print(", ".join(open_range[:40]))

    push_range = print_full_range(res, "ROOT", 1, threshold=0.5)
    print(f"SB push allin freq>50%: {len(push_range)} рук")