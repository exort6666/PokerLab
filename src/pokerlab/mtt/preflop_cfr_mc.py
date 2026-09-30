"""
Monte-Carlo DCFR для N-player префлоп-солвера (chipEV).

v6.3:
    * U_avg используется ТОЛЬКО при точном совпадении (pot, stack)
      с референсными (ref_pot, ref_stack). Иначе fallback на
      allin_equivalent.
    * Линейное масштабирование U_avg убрано — оно даёт инверсию
      (AA пушит вместо open).
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS
from pokerlab.mtt.preflop_tree import (
    PreflopNode, TreeConfig, ActionType,
    build_preflop_tree, iter_nodes, node_count,
)

log = logging.getLogger(__name__)

DCFR_ALPHA = 1.5
DCFR_BETA = 0.0
DCFR_GAMMA = 2.0

# Параметры, при которых посчитан srp_25bb_pot6_test
U_AVG_REF_POT = 6.0
U_AVG_REF_STACK = 25.0

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


def _ip_oop_from_hu(live, n_players):
    """Возвращает (ip_pos, oop_pos) для HU-пары или None."""
    if len(live) != 2:
        return None
    if n_players == 2:
        if set(live) == {"SB", "BB"}:
            return "BB", "SB"
    elif n_players == 3:
        if "BTN" in live:
            ip = "BTN"
            oop = next(p for p in live if p != "BTN")
            return ip, oop
        if set(live) == {"SB", "BB"}:
            return "BB", "SB"
    return None


@dataclass
class PreflopStrategyMC:
    strategies: dict[str, np.ndarray]
    actions_of: dict[str, list]
    node_meta: dict[str, dict]
    cfg: TreeConfig
    iterations: int
    elapsed_sec: float
    postflop_model: str = "allin_equivalent"


class PreflopSolverMC:

    def __init__(
        self,
        cfg: TreeConfig,
        evaluator: Callable[[list[str]], int] | None = None,
        seed: int = 42,
        postflop_model: str = "allin_equivalent",
        postflop_u_avg: np.ndarray | None = None,
        u_avg_ref_pot: float = U_AVG_REF_POT,
        u_avg_ref_stack: float = U_AVG_REF_STACK,
    ):
        self.cfg = cfg
        self.positions = list(cfg.positions())
        self.root = build_preflop_tree(cfg)
        self.evaluate = evaluator or _default_evaluator
        self.rng = random.Random(seed)
        self.postflop_model = postflop_model
        self.postflop_u_avg = postflop_u_avg
        self.u_avg_ref_pot = u_avg_ref_pot
        self.u_avg_ref_stack = u_avg_ref_stack

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

    def _terminal_utils(self, node, hands, board):
        u = {p: 0.0 for p in self.positions}
        pot = float(node.pot_bb)
        inv = dict(node.invested)

        if node.fold_to_win:
            winner = node.winner_if_fold
            for p in self.positions:
                u[p] = (pot - inv[p]) if p == winner else -inv[p]
            return u

        if node.allin_showdown:
            live = self._live_players(node)
            if not live:
                return u
            final_pot = pot
            final_inv = dict(inv)
            ranks = {p: self.evaluate(hands[p] + board) for p in live}
            best = min(ranks.values())
            winners = [p for p, r in ranks.items() if r == best]
            share = final_pot / len(winners)
            for p in self.positions:
                u[p] = share - final_inv[p] if p in winners else -final_inv[p]
            return u

        if node.goes_to_postflop:
            if self.postflop_u_avg is not None:
                return self._postflop_value_avg(node, hands, board)
            # Без U_avg
            if self.postflop_model == "allin_equivalent":
                return self._postflop_allin_equivalent(node, hands, board)
            # equity_only
            u = {p: 0.0 for p in self.positions}
            live = self._live_players(node)
            if not live:
                return u
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

    def _postflop_allin_equivalent(self, node, hands, board):
        """Allin-equivalent: после колла все идут allin."""
        u = {p: 0.0 for p in self.positions}
        live = self._live_players(node)
        if not live:
            return u
        S = self.cfg.stack_bb
        final_pot = float(node.pot_bb)
        final_inv = dict(node.invested)
        for p in live:
            extra = max(0.0, S - final_inv[p])
            final_pot += extra
            final_inv[p] = S
        ranks = {p: self.evaluate(hands[p] + board) for p in live}
        best = min(ranks.values())
        winners = [p for p, r in ranks.items() if r == best]
        share = final_pot / len(winners)
        for p in self.positions:
            u[p] = share - final_inv[p] if p in winners else -final_inv[p]
        return u

    def _postflop_value_avg(self, node, hands, board):
        """
        Использует U_avg ТОЛЬКО если (pot, stack) на терминале
        совпадают с референсными (ref_pot, ref_stack). Иначе —
        fallback на allin_equivalent.

        Линейное масштабирование убрано: оно давало инверсию
        (AA пушит вместо open).
        """
        u = {p: 0.0 for p in self.positions}
        live = self._live_players(node)
        if not live:
            return u

        ip_oop = _ip_oop_from_hu(live, self.cfg.n_players)
        if ip_oop is None:
            return self._postflop_allin_equivalent(node, hands, board)

        ip_pos, oop_pos = ip_oop
        pot_at_terminal = float(node.pot_bb)
        eff_stack_at_terminal = float(self.cfg.stack_bb) - max(
            float(node.invested.get(ip_pos, 0.0)),
            float(node.invested.get(oop_pos, 0.0)),
        )

        pot_match = abs(pot_at_terminal - self.u_avg_ref_pot) < 1.0
        stack_match = abs(eff_stack_at_terminal - self.u_avg_ref_stack) < 3.0

        if pot_match and stack_match:
            ip_hand = _canonical_hand(*hands[ip_pos])
            oop_hand = _canonical_hand(*hands[oop_pos])
            i_ip = self.hand_to_idx[ip_hand]
            i_oop = self.hand_to_idx[oop_hand]
            u_ip = float(self.postflop_u_avg[i_ip, i_oop])
            u[ip_pos] = u_ip
            u[oop_pos] = -u_ip
            for p in self.positions:
                if p not in live:
                    u[p] = -float(node.invested.get(p, 0.0))
            return u

        return self._postflop_allin_equivalent(node, hands, board)

    def _traverse(self, node, hands, board, t, alpha_d, beta_d):
        if node.is_terminal:
            return self._terminal_utils(node, hands, board)

        key = node.key()
        actor = node.actor
        actions = node.actions
        n_act = len(actions)

        code = _canonical_hand(*hands[actor])
        i_p = self.hand_to_idx[code]
        sigma = self._current_strategy(key)[i_p]

        u_actions = []
        for action in actions:
            child = node.children[action.short()]
            u_actions.append(self._traverse(
                child, hands, board, t, alpha_d, beta_d,
            ))

        u_node = {p: sum(sigma[a] * u_actions[a][p]
                         for a in range(n_act))
                  for p in self.positions}

        for a in range(n_act):
            delta = u_actions[a][actor] - u_node[actor]
            old = self.regret[key][i_p, a]
            new_undisc = old + delta
            if new_undisc > 0:
                self.regret[key][i_p, a] = old * alpha_d + delta
            else:
                self.regret[key][i_p, a] = old * beta_d + delta

        return u_node

    def solve(self, iterations: int = 100_000,
              log_every: int = 10_000) -> PreflopStrategyMC:
        used_model = ("u_avg" if self.postflop_u_avg is not None
                      else self.postflop_model)
        log.info("MC-DCFR (%s): %d итераций (%d-max)",
                 used_model, iterations, self.cfg.n_players)
        t0 = time.time()

        for t in range(1, iterations + 1):
            hands, board = self._sample_deal()
            alpha_d = (t ** DCFR_ALPHA) / (t ** DCFR_ALPHA + 1.0)
            beta_d = (t ** DCFR_BETA) / (t ** DCFR_BETA + 1.0)
            self._traverse(self.root, hands, board, t, alpha_d, beta_d)
            gamma_w = ((t - 1.0) / t) ** DCFR_GAMMA if t > 1 else 0.0
            for key in self.regret:
                sigma_all = self._current_strategy(key)
                self.strat_sum[key] = (
                    self.strat_sum[key] * gamma_w + sigma_all
                )
            if log_every and t % log_every == 0:
                elapsed = time.time() - t0
                rate = t / elapsed if elapsed > 0 else 0
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
                "actor": node.actor, "pot_bb": node.pot_bb,
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
            postflop_model=used_model,
        )


def validate_2max(stack: float = 10.0, iterations: int = 50_000):
    cfg = TreeConfig(
        n_players=2, stack_bb=stack, ante_bb=0.0,
        open_size=stack + 100, three_bet_size=stack + 100,
        four_bet_size=stack + 100,
    )
    solver = PreflopSolverMC(cfg, seed=42)
    res = solver.solve(iterations=iterations, log_every=0)
    sigma = res.strategies["ROOT"]
    actions = res.actions_of["ROOT"]
    idx_push = next(i for i, a in enumerate(actions)
                    if a.type == ActionType.ALLIN)
    push = [ALL_HANDS[i] for i in range(N_HANDS)
            if sigma[i, idx_push] > 0.5]
    from pokerlab.mtt.cfr_pushfold import COMBOS
    pct = sum(COMBOS[ALL_HANDS.index(h)] for h in push) / 1326.0 * 100
    print(f"[push/fold {stack} BB] push {len(push)} ({pct:.1f}%)")
    for h in ("AA", "KK", "QQ", "AKs", "72o"):
        i = ALL_HANDS.index(h)
        print(f"  {h}: push={sigma[i, idx_push]:.3f}")


def demo_3max_with_u_avg(stack: float = 20.0,
                          iterations: int = 30_000):
    from pokerlab.mtt.postflop_value import load_average_u
    u_avg = load_average_u("srp_25bb_pot6_test")
    if u_avg is None:
        print("U_avg не найден.")
        return
    print(f"Загружен U_avg shape={u_avg.shape}")

    cfg = TreeConfig(n_players=3, stack_bb=stack, ante_bb=0.0)
    solver = PreflopSolverMC(cfg, seed=42, postflop_u_avg=u_avg)
    res = solver.solve(iterations=iterations, log_every=10000)

    for key in ("ROOT", "ROOT/BTN:r2.00/BB:c",
                "ROOT/BTN:r2.00/SB:c/BB:c"):
        if key not in res.strategies:
            continue
        σ = res.strategies[key]
        actions = res.actions_of[key]
        actor = res.node_meta[key]["actor"]
        print(f"\n--- {key} (actor={actor}) ---")
        print(f"{'Hand':>6} | " + " ".join(f"{a.short():>8}"
                                            for a in actions))
        for h in ("AA", "KK", "QQ", "AKs", "AKo", "AQs",
                  "AJs", "KQo", "T9s", "72o", "32o"):
            i = ALL_HANDS.index(h)
            row = " ".join(f"{σ[i, a]:8.3f}"
                           for a in range(len(actions)))
            print(f"{h:>6} | {row}")


if __name__ == "__main__":
    import sys
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    if len(sys.argv) > 1 and sys.argv[1] == "validate":
        validate_2max(stack=10.0, iterations=50_000)
        validate_2max(stack=20.0, iterations=50_000)
    else:
        demo_3max_with_u_avg(stack=20.0, iterations=100_000)