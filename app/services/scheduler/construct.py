"""Фаза 1: построение допустимого расписания.

Жадная вставка (самые «трудные» пары первыми) + вытеснение (ejection chains) для пар,
которым не нашлось свободного места: пара занимает слот, а мешающие ей уроки уходят в очередь.
"""
from __future__ import annotations

import time
from collections import deque

from .state import State


def try_place(st: State, l: int) -> bool:
    """Ставит урок в лучший по «мягкой» стоимости слот, не трогая остальные уроки."""
    p, rng = st.p, st.rng
    g = p.lesson_g[l]
    grid = st.g_grid[g]
    best = None
    for sl in range(st.n_slots):
        if grid[sl] != -1:
            continue
        res = st.find_resources(l, sl)
        if res is None:
            continue
        t, r = res
        keys = st.keys_for(l, sl, t)
        before = st.cost(keys)
        st.assign(l, sl, t, r)
        after = st.cost(keys)
        st.unassign(l)
        score = after - before + rng.random() * 0.01
        if best is None or score < best[0]:
            best = (score, sl, t, r)
    if best is None:
        return False
    st.assign(l, best[1], best[2], best[3])
    return True


def force_place(st: State, l: int, it: int, tabu: dict[int, int]):
    """Ставит урок l, вытесняя минимум мешающих уроков. Возвращает список вытесненных
    или None, если для этого урока нет ни одного подходящего слота вообще."""
    p, rng = st.p, st.rng
    g, s = p.lesson_g[l], p.lesson_s[l]
    used = st.gs_t.get(st.gs_key[l])
    best = None
    for sl in range(st.n_slots):
        d = p.slot_day[sl]
        occ = st.g_grid[g][sl]                       # урок этой же группы в слоте — его вытесним
        kicks = set()
        if occ != -1:
            kicks.add(occ)

        # преподаватель
        free_t, busy_t = [], []
        for t in p.teachers_for_subject[s]:
            if sl in p.blocked[t]:
                continue
            o = st.t_grid[t][sl]
            if o == -1 or o == occ:
                cnt = st.t_day[t][d] - (1 if o == occ and o != -1 else 0)
                if cnt < p.max_day[t]:
                    free_t.append(t)
            else:
                busy_t.append((t, o))
        if free_t:
            t = min(free_t, key=lambda x: (0 if used and x in used else 1, st.t_load[x], rng.random()))
        elif busy_t:
            t, o = busy_t[int(rng.random() * len(busy_t))]
            kicks.add(o)
        else:
            continue

        # аудитория
        free_r, busy_r = [], []
        for r in p.rooms_for_subject[s]:
            o = st.r_grid[r][sl]
            if o == -1 or o == occ:
                free_r.append(r)
            else:
                busy_r.append((r, o))
        if free_r:
            r = free_r[int(rng.random() * len(free_r))]
        elif busy_r:
            r, o = busy_r[int(rng.random() * len(busy_r))]
            kicks.add(o)
        else:
            continue

        penalty = 10 * sum(1 for k in kicks if tabu.get(k, 0) > it)
        score = len(kicks) + penalty + rng.random() * 0.5
        if best is None or score < best[0]:
            best = (score, sl, t, r, kicks)

    if best is None:
        return None
    _, sl, t, r, kicks = best
    kicked = list(kicks)
    for k in kicked:
        st.unassign(k)
        tabu[k] = it + rng.randint(5, 20)
    st.assign(l, sl, t, r)
    return kicked


def construct(st: State, deadline: float) -> None:
    """Расставляет уроки; по выходу state содержит лучшее найденное (с минимумом непоставленных)."""
    p, rng = st.p, st.rng
    group_total = [len(x) for x in st.lessons_of_group]
    order = sorted(
        range(st.n_lessons),
        key=lambda l: (len(p.teachers_for_subject[p.lesson_s[l]]),
                       len(p.rooms_for_subject[p.lesson_s[l]]),
                       -group_total[p.lesson_g[l]], rng.random()),
    )
    pending: deque[int] = deque()
    for l in order:
        if not try_place(st, l):
            pending.append(l)
    if not pending:
        return

    best_n = len(pending)
    best_snap = st.snapshot()
    stagnation_limit = max(5000, 40 * st.n_lessons)
    since_best = 0
    tabu: dict[int, int] = {}
    impossible: set[int] = set()
    it = 0
    while pending:
        it += 1
        if (it & 31) == 0 and time.perf_counter() >= deadline:
            break
        l = pending.popleft()
        if try_place(st, l):
            continue
        kicked = force_place(st, l, it, tabu)
        if kicked is None:
            impossible.add(l)
            continue
        pending.extend(kicked)
        n = len(pending)
        if n < best_n:
            best_n, best_snap, since_best = n, st.snapshot(), 0
        else:
            since_best += 1
            if since_best > stagnation_limit:
                break
    if len(pending) > best_n:          # текущее состояние хуже лучшего — откатываемся
        st.restore(best_snap)
