"""Оркестратор решателя: построить допустимое расписание, затем улучшить его."""
from __future__ import annotations

import random
import time
from dataclasses import dataclass

from . import config as C
from .construct import construct
from .models import Problem
from .optimize import anneal
from .state import State


@dataclass(slots=True)
class Solution:
    assignments: list[tuple[int, int, int, int]]   # (урок, слот, преподаватель, аудитория)
    unplaced: list[int]                             # номера непоставленных уроков
    cost: float


def solve(p: Problem, time_limit: float = C.DEFAULT_TIME_LIMIT, seed: int | None = None) -> Solution:
    start = time.perf_counter()
    rng = random.Random(seed)
    st = State(p, rng)
    if st.n_lessons == 0 or st.n_slots == 0:
        return Solution([], list(range(st.n_lessons)), 0.0)

    construct(st, start + time_limit * C.CONSTRUCT_TIME_SHARE)

    now = time.perf_counter()
    opt_time = C.OPTIMIZE_BASE_SECONDS + C.OPTIMIZE_SECONDS_PER_LESSON * st.n_lessons
    anneal(st, min(start + time_limit, now + opt_time))

    assignments = [(l, st.slot[l], st.teacher[l], st.room[l])
                   for l in range(st.n_lessons) if st.slot[l] != -1]
    return Solution(assignments, st.unplaced(), st.total_cost())
