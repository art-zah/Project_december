"""Фаза 2: улучшение качества (имитация отжига). Допустимость при этом не нарушается."""
from __future__ import annotations

import math
import time

from . import config as C
from .state import State


def _attempt(st: State, moves, temp: float):
    """moves: [(урок, новый_слот)]. Возвращает (дельта стоимости, принято ли)."""
    rng = st.rng
    old = [(l, st.slot[l], st.teacher[l], st.room[l]) for l, _ in moves]
    for l, _, _, _ in old:
        st.unassign(l)
    new = []
    ok = True
    for (l, sl2), (_, _, t0, r0) in zip(moves, old):
        res = st.find_resources(l, sl2, t0, r0)
        if res is None:
            ok = False
            break
        st.assign(l, sl2, res[0], res[1])
        new.append((l, sl2, res[0], res[1]))
    if not ok:
        for l, _, _, _ in new:
            st.unassign(l)
        for l, sl, t, r in old:
            st.assign(l, sl, t, r)
        return 0.0, False

    keys = set()
    for l, sl, t, _ in old:
        keys.update(st.keys_for(l, sl, t))
    for l, sl, t, _ in new:
        keys.update(st.keys_for(l, sl, t))
    after = st.cost(keys)
    for l, _, _, _ in new:
        st.unassign(l)
    for l, sl, t, r in old:
        st.assign(l, sl, t, r)
    before = st.cost(keys)
    delta = after - before
    if delta <= 0 or rng.random() < math.exp(-delta / temp):
        for l, _, _, _ in old:
            st.unassign(l)
        for l, sl, t, r in new:
            st.assign(l, sl, t, r)
        return delta, True
    return 0.0, False


def anneal(st: State, deadline: float) -> None:
    rng = st.rng
    assigned = [l for l in range(st.n_lessons) if st.slot[l] != -1]
    if len(assigned) < 2 or st.n_slots < 2:
        return
    cur = st.total_cost()
    best = cur
    best_snap = st.snapshot()
    t0 = time.perf_counter()
    span = max(deadline - t0, 1e-6)
    temp = C.SA_T_START
    it = 0
    group = st.p.lesson_g
    while True:
        if (it & 63) == 0:
            now = time.perf_counter()
            if now >= deadline:
                break
            frac = (now - t0) / span
            temp = C.SA_T_START * (C.SA_T_END / C.SA_T_START) ** frac
        it += 1
        l = assigned[int(rng.random() * len(assigned))]
        sl2 = int(rng.random() * st.n_slots)
        occ = st.g_grid[group[l]][sl2]
        if occ == -1 or occ == l:
            moves = [(l, sl2)]
        else:                                   # слот занят другой парой этой группы — меняем местами
            moves = [(l, sl2), (occ, st.slot[l])]
        delta, ok = _attempt(st, moves, temp)
        if ok:
            cur += delta
            if cur < best - 1e-9:
                best = cur
                best_snap = st.snapshot()
    if cur > best + 1e-9:
        st.restore(best_snap)
