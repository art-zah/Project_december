"""Синтетические данные «как у колледжа» для проверки генератора без БД."""
from __future__ import annotations

import random
from datetime import time

from app.services.scheduler.models import (
    RawData, RawClassroom, RawSubject, RawTeacher, RawGroup, RawTimeslot,
    RawTeacherSubject, RawTeacherConstraint, RawLimit,
)

DAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]


def make_data(seed=0, n_groups=20, n_subjects=14, n_teachers=40, lessons_per_day=6,
              n_lecture=14, n_lab=8, n_gym=2, avg_per_subject=2.5, blocked_share=0.1,
              teachers_per_subject=4, days=DAYS) -> RawData:
    rnd = random.Random(seed)
    raw = RawData()
    tid = 1
    for d in days:
        for n in range(1, lessons_per_day + 1):
            raw.timeslots.append(RawTimeslot(tid, d, n, time(8 + n, 0), time(8 + n, 45)))
            tid += 1
    rid = 1
    for kind, cnt, cap in (("лекционная", n_lecture, 30), ("лаборатория", n_lab, 15), ("спортзал", n_gym, 40)):
        for i in range(cnt):
            raw.classrooms.append(RawClassroom(rid, f"{kind[:3]}-{rid}", cap, kind))
            rid += 1
    for s in range(1, n_subjects + 1):
        kind = "лаборатория" if s % 4 == 0 else ("спортзал" if s == n_subjects else "лекционная")
        raw.subjects.append(RawSubject(s, f"Предмет {s}", kind))
    for t in range(1, n_teachers + 1):
        raw.teachers.append(RawTeacher(t, f"Преподаватель {t}", rnd.choice([4, 5, 6])))
    # преподаватели раздаются по кругу, чтобы нагрузка была равномерной (как в реальном колледже)
    order = list(range(1, n_teachers + 1))
    rnd.shuffle(order)
    k = 0
    for s in range(1, n_subjects + 1):
        for _ in range(teachers_per_subject):
            raw.teacher_subjects.append(RawTeacherSubject(order[k % n_teachers], s))
            k += 1
    for g in range(1, n_groups + 1):
        raw.groups.append(RawGroup(g, f"Группа {g}", 1 + g % 4))
        subs = rnd.sample(range(1, n_subjects + 1), min(n_subjects, 10))
        for s in subs:
            n = max(1, round(rnd.gauss(avg_per_subject, 0.8)))
            raw.limits.append(RawLimit(g, s, n))
    slot_ids = [t.id for t in raw.timeslots]
    for t in range(1, n_teachers + 1):
        for sl in slot_ids:
            x = rnd.random()
            if x < blocked_share:
                raw.teacher_constraints.append(RawTeacherConstraint(sl, t, "unavailable"))
            elif x < blocked_share + 0.05:
                raw.teacher_constraints.append(RawTeacherConstraint(sl, t, "preferred"))
    return raw
