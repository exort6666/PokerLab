"""
Дерево префлоп-действий для CFR-солвера (2..9 max).

Действия: fold / call / open / 3bet / 4bet / allin.
Лимпов нет — CALL только когда был рейз.

Терминальные типы:
    * fold_to_win        — все кроме одного сфолдили
    * allin_showdown     — все живые в allin (или ровно один matched с allin'ами)
    * goes_to_postflop   — колл без allin, игра продолжается постфлоп

Каждый узел хранит dict `invested` — сколько каждый игрок вложил
на момент этого узла. Без него нельзя корректно посчитать payoff.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


MAX_DEPTH = 12


POSITIONS_BY_MAX = {
    2: ("SB", "BB"),
    3: ("BTN", "SB", "BB"),
    4: ("CO", "BTN", "SB", "BB"),
    5: ("MP", "CO", "BTN", "SB", "BB"),
    6: ("UTG", "MP", "CO", "BTN", "SB", "BB"),
    7: ("UTG", "UTG+1", "MP", "CO", "BTN", "SB", "BB"),
    8: ("UTG", "UTG+1", "MP", "MP+1", "CO", "BTN", "SB", "BB"),
    9: ("UTG", "UTG+1", "UTG+2", "MP", "MP+1",
        "CO", "BTN", "SB", "BB"),
}


# ============================================================
# Действия
# ============================================================

class ActionType(str, Enum):
    FOLD = "f"
    CALL = "c"
    OPEN = "r"
    THREE_BET = "r3"
    FOUR_BET = "r4"
    ALLIN = "a"


@dataclass
class Action:
    type: ActionType
    amount_bb: float = 0.0
    is_allin: bool = False

    def short(self) -> str:
        if self.type == ActionType.FOLD:
            return "f"
        if self.type == ActionType.CALL:
            return "c"
        if self.is_allin:
            return f"{self.type.value}ai"
        return f"{self.type.value}{self.amount_bb:.2f}"


# ============================================================
# Узел
# ============================================================

@dataclass
class PreflopNode:
    history: list[tuple[str, str]] = field(default_factory=list)
    actor: str = ""
    actions: list[Action] = field(default_factory=list)
    children: dict[str, "PreflopNode"] = field(default_factory=dict)

    # Сколько каждый игрок уже вложил (в BB, включая блайнды).
    invested: dict[str, float] = field(default_factory=dict)

    is_terminal: bool = False
    fold_to_win: bool = False
    allin_showdown: bool = False
    goes_to_postflop: bool = False

    winner_if_fold: str | None = None
    pot_bb: float = 0.0

    def key(self) -> str:
        if not self.history:
            return "ROOT"
        return "/".join(f"{p}:{a}" for p, a in self.history)


# ============================================================
# Параметры дерева
# ============================================================

@dataclass
class TreeConfig:
    n_players: int
    stack_bb: float
    ante_bb: float = 0.0
    open_size: float = 2.0
    three_bet_size: float = 6.0
    four_bet_size: float = 12.0

    def positions(self) -> tuple[str, ...]:
        return POSITIONS_BY_MAX[self.n_players]


# ============================================================
# Вспомогательное
# ============================================================

def _blinds_posted(positions: tuple[str, ...]) -> dict[str, float]:
    out = {p: 0.0 for p in positions}
    if "SB" in out:
        out["SB"] = 0.5
    if "BB" in out:
        out["BB"] = 1.0
    return out


def _starting_order(positions: tuple[str, ...]) -> list[str]:
    if len(positions) == 2:
        return ["SB", "BB"]
    core = [p for p in positions if p not in ("SB", "BB")]
    return core + ["SB", "BB"]


def _to_call(actor: str, invested: dict[str, float],
             current_bet: float) -> float:
    return max(0.0, current_bet - invested.get(actor, 0.0))


def _raise_to(actor: str, invested: dict[str, float],
              target: float, stack_bb: float) -> tuple[float, bool]:
    remaining = stack_bb - invested.get(actor, 0.0)
    if target >= remaining:
        return stack_bb, True
    return target, False


def _all_matched(invested, current_bet, folds, allin_set) -> bool:
    for p, inv in invested.items():
        if p in folds or p in allin_set:
            continue
        if inv < current_bet:
            return False
    return True


def _dedup_allins(actions: list[Action]) -> list[Action]:
    has_pure = any(
        a.type == ActionType.ALLIN and a.is_allin for a in actions
    )
    if not has_pure:
        return actions
    return [
        a for a in actions
        if not (a.is_allin and a.type != ActionType.ALLIN)
    ]


# ============================================================
# Построение дерева
# ============================================================

def build_preflop_tree(cfg: TreeConfig) -> PreflopNode:
    positions = cfg.positions()
    order = _starting_order(positions)
    blinds = _blinds_posted(positions)

    ante_total = cfg.ante_bb * cfg.n_players
    pot0 = 1.5 + ante_total

    root = PreflopNode(
        history=[],
        actor=order[0],
        pot_bb=pot0,
        invested=dict(blinds),
    )
    _expand(
        node=root,
        cfg=cfg,
        order=order,
        actor_idx=0,
        invested=dict(blinds),
        current_bet=1.0,
        last_raiser=None,
        raiser_level=0,
        folds=set(),
        allin_set=set(),
    )
    return root


def _expand(
    node: PreflopNode,
    cfg: TreeConfig,
    order: list[str],
    actor_idx: int,
    invested: dict[str, float],
    current_bet: float,
    last_raiser: str | None,
    raiser_level: int,
    folds: set[str],
    allin_set: set[str],
) -> None:
    actor = order[actor_idx]
    stack = cfg.stack_bb

    if len(node.history) > MAX_DEPTH:
        node.is_terminal = True
        node.allin_showdown = True
        return

    not_folded = [p for p in order if p not in folds]

    if len(not_folded) <= 1:
        node.is_terminal = True
        node.fold_to_win = True
        node.winner_if_fold = not_folded[0] if not_folded else None
        return

    active = [p for p in not_folded if p not in allin_set]

    if len(active) == 0:
        node.is_terminal = True
        node.allin_showdown = True
        return

    if len(active) == 1:
        solo = active[0]
        if invested[solo] >= current_bet:
            node.is_terminal = True
            node.allin_showdown = True
            return

    if actor in folds or actor in allin_set:
        node.is_terminal = True
        node.allin_showdown = True
        return

    if (last_raiser is not None
            and actor == last_raiser
            and _all_matched(invested, current_bet, folds, allin_set)):
        node.is_terminal = True
        node.goes_to_postflop = True
        node.pot_bb = (sum(invested.values())
                       + cfg.ante_bb * cfg.n_players)
        return

    to_call = _to_call(actor, invested, current_bet)
    actor_remaining = stack - invested[actor]

    actions: list[Action] = [Action(ActionType.FOLD)]

    if actor_remaining > 0:
        actions.append(Action(ActionType.ALLIN,
                              amount_bb=stack, is_allin=True))

    if raiser_level >= 1 and 0 < to_call < actor_remaining:
        actions.append(Action(ActionType.CALL, amount_bb=to_call))

    if raiser_level == 0:
        amount, is_allin = _raise_to(actor, invested,
                                     cfg.open_size, stack)
        if amount > current_bet:
            actions.append(Action(ActionType.OPEN,
                                  amount_bb=amount, is_allin=is_allin))
    elif raiser_level == 1:
        amount, is_allin = _raise_to(actor, invested,
                                     cfg.three_bet_size, stack)
        if amount > current_bet:
            actions.append(Action(ActionType.THREE_BET,
                                  amount_bb=amount, is_allin=is_allin))
    elif raiser_level == 2:
        amount, is_allin = _raise_to(actor, invested,
                                     cfg.four_bet_size, stack)
        if amount > current_bet:
            actions.append(Action(ActionType.FOUR_BET,
                                  amount_bb=amount, is_allin=is_allin))

    actions = _dedup_allins(actions)

    if not actions:
        node.is_terminal = True
        node.fold_to_win = True
        node.winner_if_fold = actor
        return

    node.actions = actions

    for act in actions:
        new_invested = dict(invested)
        new_folds = set(folds)
        new_allin = set(allin_set)

        short = act.short()

        if act.type == ActionType.FOLD:
            new_folds.add(actor)
        elif act.type == ActionType.CALL:
            delta = to_call if to_call > 0 else 0.0
            new_invested[actor] += delta
        else:
            new_invested[actor] = act.amount_bb
            if act.is_allin:
                new_allin.add(actor)

        new_current_bet = max(current_bet, new_invested[actor])

        next_idx = None
        for i in range(1, len(order) + 1):
            cand = (actor_idx + i) % len(order)
            if (order[cand] not in new_folds
                    and order[cand] not in new_allin):
                next_idx = cand
                break

        child_pot = (sum(new_invested.values())
                     + cfg.ante_bb * cfg.n_players)

        if next_idx is None:
            child = PreflopNode(
                history=node.history + [(actor, short)],
                actor=actor,
                pot_bb=child_pot,
                invested=dict(new_invested),
            )
            child.is_terminal = True
            remaining = [p for p in order if p not in new_folds]
            if len(remaining) <= 1:
                child.fold_to_win = True
                child.winner_if_fold = remaining[0] if remaining else None
            else:
                child.allin_showdown = True
            node.children[short] = child
            continue

        new_raiser_level = raiser_level
        new_last_raiser = last_raiser
        if act.type == ActionType.OPEN:
            new_raiser_level = 1
            new_last_raiser = actor
        elif act.type == ActionType.THREE_BET:
            new_raiser_level = 2
            new_last_raiser = actor
        elif act.type == ActionType.FOUR_BET:
            new_raiser_level = 3
            new_last_raiser = actor
        elif act.type == ActionType.ALLIN:
            new_raiser_level = 4
            new_last_raiser = actor

        child = PreflopNode(
            history=node.history + [(actor, short)],
            actor=order[next_idx],
            pot_bb=child_pot,
            invested=dict(new_invested),
        )
        node.children[short] = child

        _expand(
            node=child,
            cfg=cfg,
            order=order,
            actor_idx=next_idx,
            invested=new_invested,
            current_bet=new_current_bet,
            last_raiser=new_last_raiser,
            raiser_level=new_raiser_level,
            folds=new_folds,
            allin_set=new_allin,
        )


# ============================================================
# Обход
# ============================================================

def iter_nodes(root: PreflopNode):
    stack = [root]
    seen = set()
    while stack:
        node = stack.pop()
        k = node.key()
        if k in seen:
            continue
        seen.add(k)
        yield node
        for child in node.children.values():
            stack.append(child)


def node_count(root: PreflopNode) -> int:
    return sum(1 for _ in iter_nodes(root))


def terminal_count(root: PreflopNode) -> dict[str, int]:
    out = {"fold_to_win": 0, "allin_showdown": 0,
           "goes_to_postflop": 0, "non_terminal": 0}
    for n in iter_nodes(root):
        if n.is_terminal:
            if n.fold_to_win:
                out["fold_to_win"] += 1
            elif n.allin_showdown:
                out["allin_showdown"] += 1
            elif n.goes_to_postflop:
                out["goes_to_postflop"] += 1
        else:
            out["non_terminal"] += 1
    return out


# ============================================================
# Тест
# ============================================================

if __name__ == "__main__":
    import sys
    for n in (2, 3, 4, 5, 6, 7, 8, 9):
        cfg = TreeConfig(n_players=n, stack_bb=100.0, ante_bb=0.0)
        root = build_preflop_tree(cfg)
        total = node_count(root)
        terms = terminal_count(root)
        print(f"{n}-max | nodes = {total:>9} | "
              f"fold_win={terms['fold_to_win']:>7} "
              f"showdown={terms['allin_showdown']:>7} "
              f"postflop={terms['goes_to_postflop']:>7} "
              f"non_term={terms['non_terminal']:>7}",
              flush=True)
        sys.stdout.flush()

    print()
    cfg = TreeConfig(n_players=2, stack_bb=100.0)
    root = build_preflop_tree(cfg)
    print(f"ROOT actor = {root.actor}, pot = {root.pot_bb}")
    print(f"invested = {root.invested}")