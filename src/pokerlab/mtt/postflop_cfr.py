"""
Vector CFR+ / DCFR для постфлоп-дерева (один конкретный борд).

Финальная версия (v5.1 — самая быстрая из проверенных).

Скорость: ~4.7 iter/s на борде AsKsQs, 25 BB, 5517 узлов.
Дальнейшее ускорение требует батчирования по узлам одного уровня
(см. docs/backlog.md). Принимаем как есть для MVP.

Reference:
    Zinkevich et al. (2007). Regret Minimization in Games with
    Incomplete Information.
    Brown & Sandholm (2019). Discounted Regret Minimization.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import numpy as np

from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS, PI_OPP
from pokerlab.mtt.postflop_eval import rank_fast, canonical_cards
from pokerlab.mtt.postflop_tree import (
    PostflopNode, PostflopTreeConfig, PostflopAction, Street,
    build_postflop_tree, iter_nodes, count_nodes,
)

log = logging.getLogger(__name__)


PI_OPP_F32 = PI_OPP.astype(np.float32)
PI_OPP_T_F32 = np.ascontiguousarray(PI_OPP_F32.T)


def precompute_rank_table(board: list[str]) -> np.ndarray:
    ranks = np.zeros(N_HANDS, dtype=np.int64)
    for i, h in enumerate(ALL_HANDS):
        cards = canonical_cards(h, board)
        ranks[i] = rank_fast(cards, board)
    return ranks


def precompute_win_matrix(ranks: np.ndarray) -> np.ndarray:
    lt = (ranks[:, None] < ranks[None, :]).astype(np.float32)
    eq = (ranks[:, None] == ranks[None, :]).astype(np.float32)
    return lt + 0.5 * eq


@dataclass
class PostflopStrategy:
    strategies: dict[str, np.ndarray]
    actions_of: dict[str, list]
    node_meta: dict[str, dict]
    board: list[str]
    cfg: PostflopTreeConfig
    iterations: int
    elapsed_sec: float
    rank_table: np.ndarray


class PostflopSolverVector:

    def __init__(self, cfg: PostflopTreeConfig, seed: int = 42):
        self.cfg = cfg
        self.board = list(cfg.start_board)
        self.root = build_postflop_tree(cfg)

        t0 = time.time()
        self.rank_table = precompute_rank_table(self.board)
        self.win_matrix = precompute_win_matrix(self.rank_table)
        log.info("Precompute rank/win: %.2f сек", time.time() - t0)

        self.regret: dict[str, np.ndarray] = {}
        self.strat_sum: dict[str, np.ndarray] = {}
        self.actions_of: dict[str, list] = {}
        self.node_refs: dict[str, PostflopNode] = {}

        empty = 0
        for node in iter_nodes(self.root):
            node._key = node.key()
            if node.is_terminal:
                continue
            n = len(node.actions)
            if n == 0:
                node.is_terminal = True
                node.terminal_kind = "showdown"
                empty += 1
                continue
            key = node._key
            node._children_list = [
                node.children[a.value] for a in node.actions
            ]
            node._n_act = n

            self.regret[key] = np.zeros((N_HANDS, n), dtype=np.float32)
            self.strat_sum[key] = np.zeros((N_HANDS, n), dtype=np.float32)
            self.actions_of[key] = list(node.actions)
            self.node_refs[key] = node

        if empty:
            log.warning("Пустых non-terminal узлов: %d", empty)

        max_act = max((n._n_act for n in self.node_refs.values()),
                      default=1)
        self._buf_scaled = np.empty((N_HANDS, max_act), dtype=np.float32)

        self.rng = np.random.default_rng(seed)

    def _current_strategy(self, key: str) -> np.ndarray:
        r = self.regret[key]
        pos = np.maximum(r, 0.0)
        n = pos.shape[1]
        if n == 0:
            return np.zeros((N_HANDS, 0), dtype=np.float32)
        s = pos.sum(axis=1, keepdims=True)
        return np.where(s > 0, pos / np.where(s > 0, s, 1.0), 1.0 / n)

    def _terminal_u(self, node: PostflopNode) -> np.ndarray:
        cached = getattr(node, "_cached_u", None)
        if cached is not None:
            return cached

        pot = float(node.pot_bb)
        inv_ip = float(node.invested_ip)

        if node.terminal_kind == "fold":
            u = np.empty((N_HANDS, N_HANDS), dtype=np.float32)
            if node.winner_if_fold == "IP":
                u.fill(pot - inv_ip)
            else:
                u.fill(-inv_ip)
        elif node.terminal_kind in ("showdown", "allin_called"):
            u = self.win_matrix * pot - inv_ip
        else:
            raise ValueError(f"Неизвестный терминал: {node.terminal_kind}")

        node._cached_u = u
        return u

    def _cfr_pass(
        self,
        node: PostflopNode,
        reach_ip: np.ndarray,
        reach_oop: np.ndarray,
        t: int,
    ) -> np.ndarray:
        if node.is_terminal:
            return self._terminal_u(node)

        key = node._key
        n_act = node._n_act
        if n_act == 0:
            return (self.win_matrix * float(node.pot_bb)
                    - float(node.invested_ip))

        σ = self._current_strategy(key)
        actor = node.actor
        children = node._children_list

        buf = self._buf_scaled[:, :n_act]
        np.multiply(σ, t, out=buf)
        self.strat_sum[key] += buf

        u_actions = []
        if actor == "IP":
            for a_idx in range(n_act):
                new_reach_ip = reach_ip * σ[:, a_idx]
                u_actions.append(self._cfr_pass(
                    children[a_idx], new_reach_ip, reach_oop, t,
                ))
        else:
            for a_idx in range(n_act):
                new_reach_oop = reach_oop * σ[:, a_idx]
                u_actions.append(self._cfr_pass(
                    children[a_idx], reach_ip, new_reach_oop, t,
                ))

        if actor == "IP":
            u_node = σ[:, 0][:, None] * u_actions[0]
            for a_idx in range(1, n_act):
                u_node += σ[:, a_idx][:, None] * u_actions[a_idx]
        else:
            u_node = σ[:, 0][None, :] * u_actions[0]
            for a_idx in range(1, n_act):
                u_node += σ[:, a_idx][None, :] * u_actions[a_idx]

        reg = self.regret[key]
        if actor == "IP":
            weighted = PI_OPP_F32 * reach_oop[None, :]
            for a_idx in range(n_act):
                v_a = np.einsum('ij,ij->i', weighted, u_actions[a_idx])
                reg[:, a_idx] += v_a
            v_node = np.einsum('ij,ij->i', weighted, u_node)
            reg -= v_node[:, None]
        else:
            weighted = PI_OPP_T_F32 * reach_ip[:, None]
            for a_idx in range(n_act):
                v_a = -np.einsum('ij,ij->j', weighted, u_actions[a_idx])
                reg[:, a_idx] += v_a
            v_node = -np.einsum('ij,ij->j', weighted, u_node)
            reg -= v_node[:, None]

        return u_node

    def solve(self, iterations: int = 2000,
              log_every: int = 100) -> PostflopStrategy:
        log.info("Постфлоп CFR+ (v5.1): %d итераций, борд=%s",
                 iterations, "".join(self.board))
        log.info("Узлов: %d", len(self.regret))
        t0 = time.time()

        one = np.ones(N_HANDS, dtype=np.float32)

        for t in range(1, iterations + 1):
            self._cfr_pass(self.root, one, one, t)

            if log_every and t % log_every == 0:
                elapsed = time.time() - t0
                rate = t / elapsed if elapsed > 0 else 0
                eta = (iterations - t) / rate if rate > 0 else 0
                log.info("  iter %d/%d | %.1f iter/s | ETA %.0f сек",
                         t, iterations, rate, eta)

        avg_strategies = {}
        for key, ss in self.strat_sum.items():
            s = ss.sum(axis=1, keepdims=True)
            n = ss.shape[1]
            if n == 0:
                continue
            avg_strategies[key] = np.where(
                s > 0, ss / np.where(s > 0, s, 1.0), 1.0 / n
            ).astype(np.float64)

        node_meta = {}
        for node in iter_nodes(self.root):
            node_meta[node._key] = {
                "actor": node.actor,
                "pot_bb": node.pot_bb,
                "board": list(node.board),
                "street": node.street.value,
                "history": list(node.history),
                "is_terminal": node.is_terminal,
                "terminal_kind": node.terminal_kind,
                "winner_if_fold": node.winner_if_fold,
            }

        elapsed = time.time() - t0
        log.info("Готово за %.1f сек (%.1f мин)", elapsed, elapsed / 60)

        return PostflopStrategy(
            strategies=avg_strategies,
            actions_of=self.actions_of,
            node_meta=node_meta,
            board=self.board,
            cfg=self.cfg,
            iterations=iterations,
            elapsed_sec=elapsed,
            rank_table=self.rank_table,
        )


def _find_root_key(res: PostflopStrategy) -> str | None:
    for k in res.strategies:
        if not res.node_meta[k].get("history"):
            return k
    return None


def print_root_strategy(res: PostflopStrategy, top_n: int = 15) -> None:
    root_key = _find_root_key(res)
    if root_key is None:
        print("Не нашли ROOT")
        return
    σ = res.strategies[root_key]
    actions = res.actions_of[root_key]
    actor = res.node_meta[root_key]["actor"]
    print(f"--- ROOT (actor={actor}, "
          f"actions={[a.value for a in actions]}) ---")
    print(f"{'Hand':>6} | " + " ".join(f"{a.value:>6}"
                                        for a in actions))
    for i in range(min(top_n, N_HANDS)):
        row = " ".join(f"{σ[i, a]:6.3f}" for a in range(len(actions)))
        print(f"{ALL_HANDS[i]:>6} | {row}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Тест сходимости: 5000 итераций
    cfg = PostflopTreeConfig(
        start_pot_bb=6.0,
        start_stack_bb=25.0,
        start_board=["As", "Ks", "Qs"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )
    print(f"Узлов в дереве: {count_nodes(build_postflop_tree(cfg))}")

    solver = PostflopSolverVector(cfg)
    print(f"Узлов с regret: {len(solver.regret)}")

    res = solver.solve(iterations=5000, log_every=500)
    print()
    print_root_strategy(res, top_n=15)