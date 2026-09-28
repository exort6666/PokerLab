"""3-max PKO push/fold CFR+ solver."""

from __future__ import annotations

import numpy as np

from pokerlab.mtt.cfr_pushfold import ALL_HANDS, N_HANDS, EQ, PI_OPP
from pokerlab.mtt.icm import icm_equity


def compute_pushfold_pko_3max(
    stack_bb: float,
    bounties: tuple[float, float, float],
    prizes: tuple[float, float, float],
    iterations: int = 1000,
) -> dict:
    """3-max PKO push/fold CFR+."""
    S = float(stack_bb)
    B_btn, B_sb, B_bb = [float(b) for b in bounties]
    P1, P2, P3 = [float(p) for p in prizes]
    P = list(prizes)

    def icm3(s_btn, s_sb, s_bb):
        eq = icm_equity([s_btn, s_sb, s_bb], P)
        return tuple(eq)

    def hu_ev(s_a, s_b, b_a, b_b):
        """HU-for-1st $EV. Победитель: P1 + 2 × (B_self + B_opp)."""
        if s_a + s_b <= 0:
            return (P1 + P2) / 2, (P1 + P2) / 2
        x = s_a / (s_a + s_b)
        winner_a = P1 + 2.0 * (b_a + b_b)
        winner_b = P1 + 2.0 * (b_b + b_a)
        ev_a = x * winner_a + (1 - x) * P2
        ev_b = (1 - x) * winner_b + x * P2
        return ev_a, ev_b

    # Terminals
    t1 = icm3(S, S - 0.5, S + 0.5)
    t2 = icm3(S, S + 1, S - 1)
    hu_sb_wins_bb = hu_ev(2 * S, S, B_sb, B_btn)
    hu_bb_wins_sb = hu_ev(2 * S, S, B_bb, B_btn)

    t4 = icm3(S + 1.5, S - 0.5, S - 1)
    hu_btn_wins_vs_bb = hu_ev(2 * S, S, B_btn, B_sb)
    hu_bb_wins_vs_btn = hu_ev(2 * S, S, B_bb, B_sb)
    hu_btn_wins_vs_sb = hu_ev(2 * S, S, B_btn, B_bb)
    hu_sb_wins_vs_btn = hu_ev(2 * S, S, B_sb, B_bb)

    # Regrets
    reg_btn = np.zeros((N_HANDS, 2))
    reg_sb_bf = np.zeros((N_HANDS, 2))
    reg_bb_sb = np.zeros((N_HANDS, 2))
    reg_sb_bp = np.zeros((N_HANDS, 2))
    reg_bb_bp = np.zeros((N_HANDS, 2))

    ss_btn = np.zeros((N_HANDS, 2))
    ss_sb_bf = np.zeros((N_HANDS, 2))
    ss_bb_sb = np.zeros((N_HANDS, 2))
    ss_sb_bp = np.zeros((N_HANDS, 2))
    ss_bb_bp = np.zeros((N_HANDS, 2))

    def rm(r):
        pos = np.maximum(r, 0)
        s = pos.sum(axis=1, keepdims=True)
        return np.where(s > 0, pos / np.where(s > 0, s, 1), 0.5)

    for t in range(1, iterations + 1):
        st_btn = rm(reg_btn)
        st_sb_bf = rm(reg_sb_bf)
        st_bb_sb = rm(reg_bb_sb)
        st_sb_bp = rm(reg_sb_bp)
        st_bb_bp = rm(reg_bb_bp)

        ss_btn += t * st_btn
        ss_sb_bf += t * st_sb_bf
        ss_bb_sb += t * st_bb_sb
        ss_sb_bp += t * st_sb_bp
        ss_bb_bp += t * st_bb_bp

        # BB после SB push (BTN fold)
        W_bb_sb = PI_OPP * st_sb_bf[:, 1][None, :]
        p_sb_push_bb = W_bb_sb.sum(axis=1)
        eq_bb_sb = np.where(
            p_sb_push_bb > 0,
            (W_bb_sb * EQ).sum(axis=1) / np.where(p_sb_push_bb > 0, p_sb_push_bb, 1),
            0.5,
        )
        ev_bb_sb_fold = np.full(N_HANDS, t2[2])
        ev_bb_sb_call = eq_bb_sb * hu_bb_wins_sb[0] + (1 - eq_bb_sb) * P3
        ev_s = st_bb_sb[:, 0] * ev_bb_sb_fold + st_bb_sb[:, 1] * ev_bb_sb_call
        reg_bb_sb[:, 0] = np.maximum(0, reg_bb_sb[:, 0] + (ev_bb_sb_fold - ev_s))
        reg_bb_sb[:, 1] = np.maximum(0, reg_bb_sb[:, 1] + (ev_bb_sb_call - ev_s))

        # BB после BTN push, SB fold
        W_bb_btn = PI_OPP * st_btn[:, 1][None, :]
        p_btn_push_bb = W_bb_btn.sum(axis=1)
        eq_bb_btn = np.where(
            p_btn_push_bb > 0,
            (W_bb_btn * EQ).sum(axis=1) / np.where(p_btn_push_bb > 0, p_btn_push_bb, 1),
            0.5,
        )
        ev_bb_bp_fold = np.full(N_HANDS, t4[2])
        ev_bb_bp_call = eq_bb_btn * hu_bb_wins_vs_btn[0] + (1 - eq_bb_btn) * P3
        ev_s = st_bb_bp[:, 0] * ev_bb_bp_fold + st_bb_bp[:, 1] * ev_bb_bp_call
        reg_bb_bp[:, 0] = np.maximum(0, reg_bb_bp[:, 0] + (ev_bb_bp_fold - ev_s))
        reg_bb_bp[:, 1] = np.maximum(0, reg_bb_bp[:, 1] + (ev_bb_bp_call - ev_s))

        # SB после BTN fold
        W_sb_bb = PI_OPP * st_bb_sb[:, 1][None, :]
        p_bb_call = W_sb_bb.sum(axis=1)
        eq_sb_bb = np.where(
            p_bb_call > 0,
            (W_sb_bb * EQ).sum(axis=1) / np.where(p_bb_call > 0, p_bb_call, 1),
            0.5,
        )
        ev_sb_bf_fold_arr = np.full(N_HANDS, t1[1])
        ev_sb_bf_push_arr = (
            (1 - p_bb_call) * t2[1]
            + p_bb_call * (eq_sb_bb * hu_sb_wins_bb[0] + (1 - eq_sb_bb) * P3)
        )
        ev_s = st_sb_bf[:, 0] * ev_sb_bf_fold_arr + st_sb_bf[:, 1] * ev_sb_bf_push_arr
        reg_sb_bf[:, 0] = np.maximum(0, reg_sb_bf[:, 0] + (ev_sb_bf_fold_arr - ev_s))
        reg_sb_bf[:, 1] = np.maximum(0, reg_sb_bf[:, 1] + (ev_sb_bf_push_arr - ev_s))

        # SB после BTN push
        W_sb_btn = PI_OPP * st_btn[:, 1][None, :]
        p_btn_push_sb = W_sb_btn.sum(axis=1)
        eq_sb_btn = np.where(
            p_btn_push_sb > 0,
            (W_sb_btn * EQ).sum(axis=1) / np.where(p_btn_push_sb > 0, p_btn_push_sb, 1),
            0.5,
        )
        p_bb_call_avg = float(st_bb_bp[:, 1].mean())
        eq_bb_btn_avg = float(eq_bb_btn.mean()) if len(eq_bb_btn) else 0.5
        ev_bb_call_avg = (
            eq_bb_btn_avg * hu_bb_wins_vs_btn[0] + (1 - eq_bb_btn_avg) * P3
        )
        sb_fold_avg = (1 - p_bb_call_avg) * t4[1] + p_bb_call_avg * ev_bb_call_avg
        ev_sb_bp_fold_arr = np.full(N_HANDS, sb_fold_avg)
        ev_sb_bp_call_arr = (
            eq_sb_btn * hu_sb_wins_vs_btn[0] + (1 - eq_sb_btn) * P3
        )
        ev_s = st_sb_bp[:, 0] * ev_sb_bp_fold_arr + st_sb_bp[:, 1] * ev_sb_bp_call_arr
        reg_sb_bp[:, 0] = np.maximum(0, reg_sb_bp[:, 0] + (ev_sb_bp_fold_arr - ev_s))
        reg_sb_bp[:, 1] = np.maximum(0, reg_sb_bp[:, 1] + (ev_sb_bp_call_arr - ev_s))

        # BTN
        p_sb_push_avg = float(st_sb_bf[:, 1].mean())
        sb_push_bbfold_btn = t2[0]
        eq_sb_bb_avg = float(eq_sb_bb.mean()) if len(eq_sb_bb) else 0.5
        sb_push_bbcall_btn = (
            eq_sb_bb_avg * hu_sb_wins_bb[1]
            + (1 - eq_sb_bb_avg) * hu_bb_wins_sb[1]
        )
        sb_push_avg_btn = (
            (1 - p_bb_call_avg) * sb_push_bbfold_btn
            + p_bb_call_avg * sb_push_bbcall_btn
        )
        btn_fold_val = (1 - p_sb_push_avg) * t1[0] + p_sb_push_avg * sb_push_avg_btn
        ev_btn_fold_arr = np.full(N_HANDS, btn_fold_val)

        p_sb_call_given_btn = (PI_OPP * st_sb_bp[:, 1][None, :]).sum(axis=1)
        eq_btn_sb_sum = (PI_OPP * st_sb_bp[:, 1][None, :] * EQ).sum(axis=1)
        eq_btn_sb = np.where(
            p_sb_call_given_btn > 0,
            eq_btn_sb_sum / np.where(p_sb_call_given_btn > 0, p_sb_call_given_btn, 1),
            0.5,
        )
        ev_btn_sb_call = eq_btn_sb * hu_btn_wins_vs_bb[0] + (1 - eq_btn_sb) * P3

        p_bb_call_given_btn = (PI_OPP * st_bb_bp[:, 1][None, :]).sum(axis=1)
        eq_btn_bb_sum = (PI_OPP * st_bb_bp[:, 1][None, :] * EQ).sum(axis=1)
        eq_btn_bb = np.where(
            p_bb_call_given_btn > 0,
            eq_btn_bb_sum / np.where(p_bb_call_given_btn > 0, p_bb_call_given_btn, 1),
            0.5,
        )
        ev_btn_sb_fold_bbcall = eq_btn_bb * hu_btn_wins_vs_sb[0] + (1 - eq_btn_bb) * P3
        ev_btn_sb_fold = (
            (1 - p_bb_call_given_btn) * t4[0]
            + p_bb_call_given_btn * ev_btn_sb_fold_bbcall
        )
        ev_btn_push_arr = (
            p_sb_call_given_btn * ev_btn_sb_call
            + (1 - p_sb_call_given_btn) * ev_btn_sb_fold
        )

        ev_s = st_btn[:, 0] * ev_btn_fold_arr + st_btn[:, 1] * ev_btn_push_arr
        reg_btn[:, 0] = np.maximum(0, reg_btn[:, 0] + (ev_btn_fold_arr - ev_s))
        reg_btn[:, 1] = np.maximum(0, reg_btn[:, 1] + (ev_btn_push_arr - ev_s))

    def avg(ss):
        return ss / ss.sum(axis=1, keepdims=True)

    def rng(p):
        return [ALL_HANDS[i] for i in range(N_HANDS) if p[i] > 0.5]

    a_btn = avg(ss_btn)
    a_sb_bf = avg(ss_sb_bf)
    a_bb_sb = avg(ss_bb_sb)
    a_sb_bp = avg(ss_sb_bp)
    a_bb_bp = avg(ss_bb_bp)

    return {
        "btn_push": rng(a_btn[:, 1]),
        "sb_push_after_btnfold": rng(a_sb_bf[:, 1]),
        "bb_call_after_sbpush": rng(a_bb_sb[:, 1]),
        "sb_call_after_btnpush": rng(a_sb_bp[:, 1]),
        "bb_call_after_btnpush_sbfold": rng(a_bb_bp[:, 1]),
    }


def _count_combos(hands):
    total = 0
    for h in hands:
        if h[0] == h[1]:
            total += 6
        elif h.endswith("s"):
            total += 4
        else:
            total += 12
    return total


def print_3max_result(label: str, result: dict) -> None:
    print(f"=== {label} ===")
    for key, hands in result.items():
        combos = _count_combos(hands)
        print(f"  {key:32s} {combos/1326*100:5.1f}% ({len(hands)} рук)")
    print()