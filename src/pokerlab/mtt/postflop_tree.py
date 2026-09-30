"""
Дерево постфлоп-действий для CFR-солвера.

Улицы: FLOP → TURN → RIVER → SHOWDOWN.

Действия:
    CHECK, BET_33, BET_50, BET_75, BET_ALLIN,
    CALL, RAISE_25, RAISE_ALLIN, FOLD.

Размеры:
    Flop/Turn/River: 33%, 50%, 75% от пота.
    Raise: 2.5 × (последняя ставка).
    Max рейзов на улице: 2.

Терминалы:
    fold_to_win      — все сфолдили, кроме одного.
    showdown         — ривер закончился без фолда.
    allin_called     — allin заколлирован (вскрытие).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Street(str, Enum):
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"


def _next_street(street: Street) -> Street | None:
    if street == Street.FLOP:
        return Street.TURN
    if street == Street.TURN:
        return Street.RIVER
    return None


class PostflopAction(str, Enum):
    CHECK = "x"
    BET_33 = "b33"
    BET_50 = "b50"
    BET_75 = "b75"
    BET_ALLIN = "bAI"
    CALL = "c"
    RAISE_25 = "r25"
    RAISE_ALLIN = "rAI"
    FOLD = "f"


# Согласованные размеры: 33%, 50%, 75%
BET_FRACTIONS = [0.33, 0.50, 0.75]


def _bet_action_from_frac(frac: float) -> PostflopAction:
    if abs(frac - 0.33) < 1e-6:
        return PostflopAction.BET_33
    if abs(frac - 0.50) < 1e-6:
        return PostflopAction.BET_50
    if abs(frac - 0.75) < 1e-6:
        return PostflopAction.BET_75
    raise ValueError(f"Неизвестная доля пота: {frac}")


@dataclass
class PostflopNode:
    street: Street
    actor: str

    board: list[str] = field(default_factory=list)

    pot_bb: float = 0.0
    invested_ip: float = 0.0
    invested_oop: float = 0.0
    stack_ip: float = 0.0
    stack_oop: float = 0.0

    street_inv_ip: float = 0.0
    street_inv_oop: float = 0.0
    street_bet: float = 0.0
    street_raises: int = 0
    checked_once: bool = False

    actions: list[PostflopAction] = field(default_factory=list)
    children: dict[str, "PostflopNode"] = field(default_factory=dict)
    history: list[tuple[str, str, str]] = field(default_factory=list)

    is_terminal: bool = False
    terminal_kind: str | None = None
    winner_if_fold: str | None = None

    def key(self, prefix: str = "") -> str:
        if not self.history:
            return f"{prefix}|{self.street.value}|{self.actor}"
        hist = "/".join(f"{s}:{a}:{act}"
                        for s, a, act in self.history)
        return f"{prefix}|{hist}"


@dataclass
class PostflopTreeConfig:
    start_pot_bb: float
    start_stack_bb: float
    start_board: list[str]
    start_street: Street
    start_actor: str
    bet_fractions: list[float] = field(
        default_factory=lambda: [0.33, 0.50, 0.75]
    )
    raise_multiplier: float = 2.5
    max_raises_per_street: int = 2
    eps: float = 1e-6


def _other(actor: str) -> str:
    return "OOP" if actor == "IP" else "IP"


def _actor_field(node: PostflopNode, actor: str, attr: str) -> float:
    return getattr(node, f"{attr}_{actor.lower()}")


def build_postflop_tree(cfg: PostflopTreeConfig) -> PostflopNode:
    root = PostflopNode(
        street=cfg.start_street,
        actor=cfg.start_actor,
        board=list(cfg.start_board),
        pot_bb=cfg.start_pot_bb,
        stack_ip=cfg.start_stack_bb,
        stack_oop=cfg.start_stack_bb,
    )
    _expand(root, cfg)
    return root


def _expand(node: PostflopNode, cfg: PostflopTreeConfig) -> None:
    if node.is_terminal:
        return

    actor = node.actor
    my_stack = _actor_field(node, actor, "stack")

    if my_stack <= cfg.eps:
        _go_to_next_street(node, cfg)
        return

    actions: list[PostflopAction] = []

    if node.street_bet == 0.0:
        actions.append(PostflopAction.CHECK)
        for frac in cfg.bet_fractions:
            amount = node.pot_bb * frac
            if amount >= my_stack:
                continue
            actions.append(_bet_action_from_frac(frac))
        actions.append(PostflopAction.BET_ALLIN)
    else:
        to_call = node.street_bet - _actor_field(
            node, actor, "street_inv"
        )
        actions.append(PostflopAction.FOLD)
        if to_call < my_stack - cfg.eps:
            actions.append(PostflopAction.CALL)
        else:
            actions.append(PostflopAction.CALL)

        if node.street_raises < cfg.max_raises_per_street:
            raise_to = node.street_bet * cfg.raise_multiplier
            delta_needed = raise_to - _actor_field(
                node, actor, "street_inv"
            )
            if 0 < delta_needed < my_stack - cfg.eps:
                actions.append(PostflopAction.RAISE_25)
            actions.append(PostflopAction.RAISE_ALLIN)

    node.actions = actions

    for action in actions:
        child = _apply_action(node, action, cfg)
        if child is None:
            continue
        node.children[action.value] = child
        _expand(child, cfg)


def _apply_action(parent: PostflopNode,
                  action: PostflopAction,
                  cfg: PostflopTreeConfig) -> PostflopNode | None:
    actor = parent.actor
    other = _other(actor)
    my_stack = _actor_field(parent, actor, "stack")
    my_inv_street = _actor_field(parent, actor, "street_inv")

    child = PostflopNode(
        street=parent.street,
        actor=other,
        board=list(parent.board),
        pot_bb=parent.pot_bb,
        invested_ip=parent.invested_ip,
        invested_oop=parent.invested_oop,
        stack_ip=parent.stack_ip,
        stack_oop=parent.stack_oop,
        street_inv_ip=parent.street_inv_ip,
        street_inv_oop=parent.street_inv_oop,
        street_bet=parent.street_bet,
        street_raises=parent.street_raises,
        checked_once=parent.checked_once,
        history=parent.history + [
            (parent.street.value, actor, action.value)
        ],
    )

    if action == PostflopAction.FOLD:
        child.is_terminal = True
        child.terminal_kind = "fold"
        child.winner_if_fold = other
        return child

    if action == PostflopAction.CHECK:
        if parent.checked_once:
            return _go_to_next_street(child, cfg)
        child.checked_once = True
        return child

    if action in (PostflopAction.BET_33,
                  PostflopAction.BET_50,
                  PostflopAction.BET_75):
        frac = {
            PostflopAction.BET_33: 0.33,
            PostflopAction.BET_50: 0.50,
            PostflopAction.BET_75: 0.75,
        }[action]
        amount = min(parent.pot_bb * frac, my_stack)
        child = _apply_money(child, actor, amount)
        child.street_bet = _actor_field(child, actor, "street_inv")
        child.checked_once = False
        if child.stack_ip <= cfg.eps or child.stack_oop <= cfg.eps:
            child.is_terminal = True
            child.terminal_kind = "allin_called"
        return child

    if action == PostflopAction.BET_ALLIN:
        amount = my_stack
        child = _apply_money(child, actor, amount)
        child.street_bet = 1e9
        child.checked_once = False
        return child

    if action == PostflopAction.CALL:
        to_call = parent.street_bet - my_inv_street
        to_call = max(0.0, min(to_call, my_stack))
        child = _apply_money(child, actor, to_call)
        return _go_to_next_street(child, cfg)

    if action == PostflopAction.RAISE_25:
        target = parent.street_bet * cfg.raise_multiplier
        delta = max(0.0, min(target - my_inv_street, my_stack))
        child = _apply_money(child, actor, delta)
        child.street_bet = _actor_field(child, actor, "street_inv")
        child.street_raises = parent.street_raises + 1
        child.checked_once = False
        if child.stack_ip <= cfg.eps or child.stack_oop <= cfg.eps:
            child.is_terminal = True
            child.terminal_kind = "allin_called"
        return child

    if action == PostflopAction.RAISE_ALLIN:
        delta = my_stack
        child = _apply_money(child, actor, delta)
        child.street_bet = 1e9
        child.street_raises = parent.street_raises + 1
        child.checked_once = False
        return child

    raise ValueError(f"Неизвестное действие: {action}")


def _apply_money(node: PostflopNode, actor: str,
                 amount: float) -> PostflopNode:
    stack_attr = f"stack_{actor.lower()}"
    inv_attr = f"invested_{actor.lower()}"
    str_attr = f"street_inv_{actor.lower()}"

    setattr(node, stack_attr, getattr(node, stack_attr) - amount)
    setattr(node, inv_attr, getattr(node, inv_attr) + amount)
    setattr(node, str_attr, getattr(node, str_attr) + amount)
    node.pot_bb += amount
    return node


def _go_to_next_street(node: PostflopNode,
                       cfg: PostflopTreeConfig) -> PostflopNode:
    nxt = _next_street(node.street)
    if nxt is None:
        node.is_terminal = True
        node.terminal_kind = "showdown"
        node.actions = []
        node.children = {}
        return node

    node.street = nxt
    node.actor = "OOP"
    node.street_inv_ip = 0.0
    node.street_inv_oop = 0.0
    node.street_bet = 0.0
    node.street_raises = 0
    node.checked_once = False
    node.actions = []
    node.children = {}
    node.is_terminal = False
    node.terminal_kind = None
    node.winner_if_fold = None

    _expand(node, cfg)
    return node


def iter_nodes(root: PostflopNode):
    stack = [root]
    seen = set()
    while stack:
        n = stack.pop()
        if id(n) in seen:
            continue
        seen.add(id(n))
        yield n
        for c in n.children.values():
            stack.append(c)


def count_nodes(root: PostflopNode) -> int:
    return sum(1 for _ in iter_nodes(root))


def count_terminals(root: PostflopNode) -> dict:
    out = {"fold": 0, "showdown": 0, "allin_called": 0,
           "non_terminal": 0, "empty_actions": 0}
    for n in iter_nodes(root):
        if n.is_terminal:
            if n.terminal_kind:
                out[n.terminal_kind] = out.get(n.terminal_kind, 0) + 1
        else:
            out["non_terminal"] += 1
            if not n.actions:
                out["empty_actions"] += 1
    return out


if __name__ == "__main__":
    print("=== HU SRP, 25 BB, флоп AsKsQs ===")
    cfg = PostflopTreeConfig(
        start_pot_bb=6.0,
        start_stack_bb=25.0,
        start_board=["As", "Ks", "Qs"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )
    root = build_postflop_tree(cfg)
    print(f"Узлов: {count_nodes(root)}")
    print(f"Терминалов: {count_terminals(root)}")

    print()
    print("=== HU SRP, 100 BB, флоп AsKsQs ===")
    cfg2 = PostflopTreeConfig(
        start_pot_bb=6.5,
        start_stack_bb=97.0,
        start_board=["As", "Ks", "Qs"],
        start_street=Street.FLOP,
        start_actor="OOP",
    )
    root2 = build_postflop_tree(cfg2)
    print(f"Узлов: {count_nodes(root2)}")
    print(f"Терминалов: {count_terminals(root2)}")