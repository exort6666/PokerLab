"""
Оценка реальных постфлоп-решений Hero против солвера.

Берёт первые N раздач с флопа, запускает PostflopSolverVector
на их борде и (pot, stack), находит решение Hero в дереве,
сравнивает с солвером.

Запуск:
    python tools/evaluate_sample_hands.py 3       # 3 раздачи
    python tools/evaluate_sample_hands.py 3 300   # 3 раздачи, 300 iter
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pokerlab.analysis.postflop_spots import (
    extract_all, HeroPostflopDecision, PostflopSpotType,
)
from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS
from pokerlab.mtt.postflop_cfr import PostflopSolverVector
from pokerlab.mtt.postflop_tree import (
    PostflopTreeConfig, Street, PostflopAction,
)

log = logging.getLogger(__name__)


# ============================================================
# Маппинг hero_action → PostflopAction (грубо)
# ============================================================

def _action_str_to_solver(action_str: str,
                          amount_bb: float,
                          pot_bb: float) -> str:
    """
    Грубое сопоставление действий Hero действиям солвера:
        check              → "x"
        bet  до 40% пота   → "b33"
        bet  40-60% пота   → "b50"
        bet  60-90% пота   → "b75"
        bet  > 90% пота    → "bAI"
        call               → "c"
        raise              → "r25" или "rAI"
        fold               → "f"
    """
    a = action_str.lower()
    if a == "check":
        return "x"
    if a == "fold":
        return "f"
    if a == "call":
        return "c"
    if a in ("bet", "raise"):
        if pot_bb <= 0:
            return "b33"
        frac = amount_bb / pot_bb
        if a == "raise":
            return "rAI" if frac > 1.0 else "r25"
        # bet
        if frac < 0.40:
            return "b33"
        if frac < 0.60:
            return "b50"
        if frac < 0.90:
            return "b75"
        return "bAI"
    return "?"


def _hand_to_idx(cards: str) -> int | None:
    """'AsKd' → индекс в ALL_HANDS."""
    if not cards or len(cards) != 4:
        return None
    r1, s1 = cards[0], cards[1]
    r2, s2 = cards[2], cards[3]
    ranks = "AKQJT98765432"
    if ranks.index(r1) > ranks.index(r2):
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    if r1 == r2:
        code = r1 + r2
    elif s1 == s2:
        code = r1 + r2 + "s"
    else:
        code = r1 + r2 + "o"
    try:
        return ALL_HANDS.index(code)
    except ValueError:
        return None


def _find_root_key(strategies, node_meta) -> str | None:
    for k in strategies:
        if not node_meta[k].get("history"):
            return k
    return None


# ============================================================
# Оценка одной раздачи
# ============================================================

def evaluate_one(d: HeroPostflopDecision,
                 iterations: int = 300) -> dict | None:
    """Возвращает dict с оценкой или None, если не можем оценить."""

    # Только флоп и HU/SRP
    if d.street != "flop":
        return None
    if d.spot_type not in (PostflopSpotType.SRP, PostflopSpotType.THREE_BET):
        return None
    if len(d.board_at_decision) != 3:
        return None

    # Параметры солвера
    cfg = PostflopTreeConfig(
        start_pot_bb=d.pot_at_decision,
        start_stack_bb=d.effective_stack_bb,
        start_board=list(d.board_at_decision),
        start_street=Street.FLOP,
        start_actor=d.hero_role,   # если Hero OOP — он ходит первым
    )

    t0 = time.time()
    solver = PostflopSolverVector(cfg)
    res = solver.solve(iterations=iterations, log_every=0)
    elapsed = time.time() - t0

    # Находим корневой узел
    root_key = _find_root_key(res.strategies, res.node_meta)
    if root_key is None:
        return None
    root_actor = res.node_meta[root_key]["actor"]

    # Hero всегда ходит первым на флопе в OOP.
    # Если Hero=IP — в корне дерева ходит OOP, нужно искать узел
    # после check OOP.
    if d.hero_role != root_actor:
        # Ищем узел, где актор == Hero и история заканчивается на x
        hero_key = None
        for k in res.strategies:
            meta = res.node_meta[k]
            if (meta.get("actor") == d.hero_role
                    and meta.get("history")
                    and meta["history"][-1][2] == "x"):
                hero_key = k
                break
        if hero_key is None:
            return None
        node_key = hero_key
    else:
        node_key = root_key

    sigma = res.strategies[node_key]
    actions = res.actions_of[node_key]
    action_strs = [a.value for a in actions]

    # Индекс руки Hero
    h_idx = _hand_to_idx(d.hero_cards)
    if h_idx is None:
        return None

    hero_probs = {a.value: float(sigma[h_idx, i])
                  for i, a in enumerate(actions)}

    # Действие Hero по нашей грубой классификации
    solver_act = _action_str_to_solver(
        d.hero_action, d.hero_amount_bb, d.pot_at_decision
    )

    # Оптимальное действие = argmax
    best_idx = int(np.argmax(sigma[h_idx]))
    optimal = actions[best_idx].value

    is_correct = (solver_act == optimal)

    return {
        "hand_id": d.hand_id,
        "board": "".join(d.board_at_decision),
        "hero_cards": d.hero_cards,
        "hero_role": d.hero_role,
        "pot_bb": d.pot_at_decision,
        "eff_bb": d.effective_stack_bb,
        "hero_action": d.hero_action,
        "solver_action_classified": solver_act,
        "optimal_action": optimal,
        "action_probs": hero_probs,
        "is_correct": is_correct,
        "solver_elapsed_sec": elapsed,
        "iterations": iterations,
    }


# ============================================================
# Main
# ============================================================

def main() -> None:
    n_hands = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    iterations = int(sys.argv[2]) if len(sys.argv) > 2 else 300

    logging.basicConfig(level=logging.WARNING)

    print(f"Загружаю решения Hero (ищу первые {n_hands * 10} флопов)...")
    all_decisions = extract_all(limit=2000, hu_only=True)

    # Только флоп + SRP/3BP
    flop_decisions = [
        d for d in all_decisions
        if d.street == "flop"
        and d.spot_type in (PostflopSpotType.SRP, PostflopSpotType.THREE_BET)
    ]
    print(f"Найдено валидных флопов: {len(flop_decisions)}")
    print()

    if not flop_decisions:
        print("Нет валидных раздач")
        return

    print(f"Беру первые {n_hands} раздач.")
    print(f"Итераций на раздачу: {iterations}")
    print()

    results = []
    for i, d in enumerate(flop_decisions[:n_hands], 1):
        print(f"[{i}/{n_hands}] {d.hand_id} | "
              f"{d.spot_type.value[9:]} | {d.hero_role} | "
              f"{d.hero_cards} | board={''.join(d.board_at_decision)} | "
              f"pot={d.pot_at_decision} | eff={d.effective_stack_bb}",
              flush=True)
        r = evaluate_one(d, iterations=iterations)
        if r is None:
            print(f"    пропущено (не оценено)")
            continue
        results.append(r)
        mark = "✓" if r["is_correct"] else "✗"
        print(f"    {mark} Hero={r['hero_action']} "
              f"(~{r['solver_action_classified']}) | "
              f"optimal={r['optimal_action']}")
        print(f"       probs: " + " ".join(
            f"{k}={v:.2f}" for k, v in sorted(r["action_probs"].items())
        ))
        print(f"       solver took {r['solver_elapsed_sec']:.1f}s")
        print()

    # Сводка
    n_ok = sum(1 for r in results if r["is_correct"])
    print("=" * 60)
    print(f"Итого: {len(results)} раздач")
    print(f"Совпало с солвером: {n_ok} / {len(results)}")
    if results:
        avg_time = np.mean([r["solver_elapsed_sec"] for r in results])
        print(f"Среднее время солвера: {avg_time:.1f} сек на раздачу")


if __name__ == "__main__":
    main()