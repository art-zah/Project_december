"""Независимая проверка готового расписания по жёстким правилам (не использует код решателя).
Вызывается перед записью в БД: некорректное расписание в таблицу не попадёт."""
from __future__ import annotations

from collections import Counter

from . import config as C
from .models import RawData


def _norm(v) -> str:
    return (str(v) if v is not None else "").strip().casefold()


def verify_rows(raw: RawData, rows: list[dict]) -> list[str]:
    errors: list[str] = []
    teachers = {t.id: t for t in raw.teachers}
    subjects = {s.id: s for s in raw.subjects}
    rooms = {r.id: r for r in raw.classrooms}
    slots = {t.id: t for t in raw.timeslots}
    groups = {g.id for g in raw.groups}
    can_teach = {(x.teacher_id, x.subject_id) for x in raw.teacher_subjects}
    limits = {(x.group_id, x.subject_id): x.max_lessons_per_week for x in raw.limits}
    blocked = set()
    for c in raw.teacher_constraints:
        k = _norm(c.constraint_type)
        if k not in C.PREFERRED_CONSTRAINT_TYPES and k not in C.AVOID_CONSTRAINT_TYPES:
            blocked.add((c.teacher_id, c.timeslot_id))

    seen_g, seen_t, seen_r = set(), set(), set()
    per_gs = Counter()
    per_t_day = Counter()
    for r in rows:
        g, s, t, c, ts = r["group_id"], r["subject_id"], r["teacher_id"], r["classroom_id"], r["timeslot_id"]
        if g not in groups or s not in subjects or t not in teachers or c not in rooms or ts not in slots:
            errors.append(f"строка {r}: ссылка на несуществующую сущность")
            continue
        if (g, ts) in seen_g:
            errors.append(f"группа {g} дважды в слоте {ts}")
        if (t, ts) in seen_t:
            errors.append(f"преподаватель {t} дважды в слоте {ts}")
        if (c, ts) in seen_r:
            errors.append(f"аудитория {c} дважды в слоте {ts}")
        seen_g.add((g, ts)); seen_t.add((t, ts)); seen_r.add((c, ts))
        if (t, s) not in can_teach:
            errors.append(f"преподаватель {t} не ведёт предмет {s}")
        if _norm(rooms[c].room_type) != _norm(subjects[s].room_type):
            errors.append(f"аудитория {c} не подходит по типу для предмета {s}")
        if (t, ts) in blocked:
            errors.append(f"преподаватель {t} недоступен в слоте {ts}")
        per_gs[(g, s)] += 1
        per_t_day[(t, _norm(slots[ts].day_of_week))] += 1
    for key, n in per_gs.items():
        if n > limits.get(key, 0):
            errors.append(f"группа/предмет {key}: поставлено {n}, лимит {limits.get(key, 0)}")
    for (t, day), n in per_t_day.items():
        if n > teachers[t].max_lessons_per_day:
            errors.append(f"преподаватель {t}: {n} пар в день {day}, лимит {teachers[t].max_lessons_per_day}")
    return errors
