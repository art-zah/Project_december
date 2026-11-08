"""Состояние расписания в памяти + стоимость «мягких» критериев.

Жёсткие ограничения (группа/преподаватель/аудитория не в двух местах сразу, преподаватель ведёт
свой предмет и не в запрещённое время, лимит пар в день, тип аудитории) гарантируются тем, что
все изменения проходят только через assign()/find_resources().
"""
from __future__ import annotations

import random

from . import config as C
from .models import Problem


class State:
    def __init__(self, p: Problem, rng: random.Random):
        self.p = p
        self.rng = rng
        self.n_slots = len(p.slots)
        self.n_lessons = len(p.lesson_g)
        self.gs_key = [(p.lesson_g[l], p.lesson_s[l]) for l in range(self.n_lessons)]
        self.lessons_of_group: list[list[int]] = [[] for _ in p.group_ids]
        for l, g in enumerate(p.lesson_g):
            self.lessons_of_group[g].append(l)
        self.reset()

    # ---------------------------------------------------------------- базовые операции
    def reset(self) -> None:
        p = self.p
        nS = self.n_slots
        self.g_grid = [[-1] * nS for _ in p.group_ids]
        self.t_grid = [[-1] * nS for _ in p.teacher_ids]
        self.r_grid = [[-1] * nS for _ in p.room_ids]
        self.slot = [-1] * self.n_lessons
        self.teacher = [-1] * self.n_lessons
        self.room = [-1] * self.n_lessons
        self.t_day = [[0] * max(p.n_days, 1) for _ in p.teacher_ids]
        self.t_load = [0] * len(p.teacher_ids)
        self.gs_t: dict[tuple[int, int], dict[int, int]] = {}

    def assign(self, l: int, sl: int, t: int, r: int) -> None:
        g = self.p.lesson_g[l]
        self.g_grid[g][sl] = l
        self.t_grid[t][sl] = l
        self.r_grid[r][sl] = l
        self.slot[l], self.teacher[l], self.room[l] = sl, t, r
        self.t_day[t][self.p.slot_day[sl]] += 1
        self.t_load[t] += 1
        d = self.gs_t.setdefault(self.gs_key[l], {})
        d[t] = d.get(t, 0) + 1

    def unassign(self, l: int) -> None:
        sl, t, r = self.slot[l], self.teacher[l], self.room[l]
        g = self.p.lesson_g[l]
        self.g_grid[g][sl] = -1
        self.t_grid[t][sl] = -1
        self.r_grid[r][sl] = -1
        self.slot[l] = self.teacher[l] = self.room[l] = -1
        self.t_day[t][self.p.slot_day[sl]] -= 1
        self.t_load[t] -= 1
        key = self.gs_key[l]
        d = self.gs_t[key]
        d[t] -= 1
        if d[t] == 0:
            del d[t]
            if not d:
                del self.gs_t[key]

    def snapshot(self):
        return (self.slot[:], self.teacher[:], self.room[:])

    def restore(self, snap) -> None:
        slot, teacher, room = snap
        self.reset()
        for l in range(self.n_lessons):
            if slot[l] != -1:
                self.assign(l, slot[l], teacher[l], room[l])

    def unplaced(self) -> list[int]:
        return [l for l in range(self.n_lessons) if self.slot[l] == -1]

    # ---------------------------------------------------------------- подбор ресурсов
    def find_resources(self, l: int, sl: int, pref_t: int = -1, pref_r: int = -1):
        """(преподаватель, аудитория) для урока l в слоте sl без вытеснения других уроков, либо None.
        Группа должна быть свободна в sl — это проверяет вызывающий код."""
        p = self.p
        s = p.lesson_s[l]
        d = p.slot_day[sl]
        used = self.gs_t.get(self.gs_key[l])
        rnd = self.rng.random

        best_t, best_key = -1, None
        for t in p.teachers_for_subject[s]:
            if self.t_grid[t][sl] != -1 or sl in p.blocked[t] or self.t_day[t][d] >= p.max_day[t]:
                continue
            rank = 0 if t == pref_t else (1 if used and t in used else 2)
            key = (rank, self.t_load[t], rnd())
            if best_key is None or key < best_key:
                best_t, best_key = t, key
        if best_t == -1:
            return None

        free_rooms = [r for r in p.rooms_for_subject[s] if self.r_grid[r][sl] == -1]
        if not free_rooms:
            return None
        if pref_r in free_rooms:
            best_r = pref_r
        else:
            best_r = free_rooms[int(rnd() * len(free_rooms))]
        return best_t, best_r

    # ---------------------------------------------------------------- стоимость
    def group_day_cost(self, g: int, d: int) -> float:
        grid = self.g_grid[g]
        lesson_s = self.p.lesson_s
        cnt = 0
        first = last = -1
        possum = 0
        items = None
        for pos, sl in enumerate(self.p.day_slots[d]):
            l = grid[sl]
            if l != -1:
                if cnt == 0:
                    first = pos
                last = pos
                cnt += 1
                possum += pos
                if items is None:
                    items = []
                items.append((lesson_s[l], pos))
        if cnt == 0:
            return 0.0
        cost = (
            C.W_GROUP_GAP * (last - first + 1 - cnt)
            + C.W_GROUP_LATE_START * first
            + C.W_GROUP_LOAD * cnt * cnt
            + C.W_GROUP_POS * possum
        )
        if cnt > 1:
            # один и тот же предмет несколько раз в день
            by_subject: dict[int, list[int]] = {}
            for s, pos in items:
                by_subject.setdefault(s, []).append(pos)
            for poss in by_subject.values():
                if len(poss) > 1:
                    poss.sort()
                    for a, b in zip(poss, poss[1:]):
                        cost += C.W_SAME_SUBJECT_ADJ if b - a == 1 else C.W_SAME_SUBJECT_DAY
        return cost

    def teacher_day_cost(self, t: int, d: int) -> float:
        grid = self.t_grid[t]
        pref, avoid = self.p.preferred[t], self.p.avoid[t]
        cnt = 0
        first = last = -1
        bonus = 0.0
        for pos, sl in enumerate(self.p.day_slots[d]):
            if grid[sl] != -1:
                if cnt == 0:
                    first = pos
                last = pos
                cnt += 1
                if sl in pref:
                    bonus -= C.W_PREFERRED_BONUS
                elif sl in avoid:
                    bonus += C.W_AVOID_PENALTY
        if cnt == 0:
            return 0.0
        return C.W_TEACHER_GAP * (last - first + 1 - cnt) + bonus

    def gs_cost(self, g: int, s: int) -> float:
        d = self.gs_t.get((g, s))
        return C.W_TEACHER_CHANGE * (len(d) - 1) if d else 0.0

    def cost(self, keys) -> float:
        total = 0.0
        for k in keys:
            kind = k[0]
            if kind == "g":
                total += self.group_day_cost(k[1], k[2])
            elif kind == "t":
                total += self.teacher_day_cost(k[1], k[2])
            else:
                total += self.gs_cost(k[1], k[2])
        return total

    def total_cost(self) -> float:
        p = self.p
        total = 0.0
        for g in range(len(p.group_ids)):
            for d in range(p.n_days):
                total += self.group_day_cost(g, d)
        for t in range(len(p.teacher_ids)):
            for d in range(p.n_days):
                total += self.teacher_day_cost(t, d)
        for (g, s) in self.gs_t:
            total += self.gs_cost(g, s)
        return total

    def keys_for(self, l: int, sl: int, t: int):
        """Ключи стоимости, которые затрагивает урок l, стоящий в слоте sl у преподавателя t."""
        g, s = self.gs_key[l]
        d = self.p.slot_day[sl]
        return (("g", g, d), ("t", t, d), ("s", g, s))
