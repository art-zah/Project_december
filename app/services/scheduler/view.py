"""Подготовка расписания к показу: превращает строки schedules в сетку «пара × день».
Чистая функция без БД и без веб-фреймворка — легко тестировать."""
from __future__ import annotations

from .models import RawData
from .problem import _norm, _day_order

VIEWS = {"group": "Группы", "teacher": "Преподаватели", "classroom": "Аудитории"}


def _fmt_time(t) -> str:
    return t.strftime("%H:%M") if hasattr(t, "strftime") else str(t)[:5]


def entity_options(raw: RawData, view: str) -> list[tuple[int, str]]:
    if view == "teacher":
        return sorted(((t.id, t.name) for t in raw.teachers), key=lambda x: x[1])
    if view == "classroom":
        return sorted(((r.id, f"{r.room_number} ({r.room_type})") for r in raw.classrooms), key=lambda x: x[1])
    return sorted(((g.id, f"{g.name} ({g.course} курс)") for g in raw.groups), key=lambda x: x[1])


def build_grid(raw: RawData, rows: list[dict], view: str, entity_id: int) -> dict:
    """Сетка для одной группы / преподавателя / аудитории.
    Возвращает {"days": [...], "lessons": [{"number", "time", "cells": [[cell,...] на каждый день]}]}."""
    if view not in VIEWS:
        view = "group"
    key = {"group": "group_id", "teacher": "teacher_id", "classroom": "classroom_id"}[view]

    names = {
        "group": {g.id: g.name for g in raw.groups},
        "teacher": {t.id: t.name for t in raw.teachers},
        "classroom": {r.id: r.room_number for r in raw.classrooms},
        "subject": {s.id: s.name for s in raw.subjects},
    }

    # дни — по порядку недели; неизвестные названия — после известных
    day_keys: dict[str, str] = {}
    for ts in sorted(raw.timeslots, key=lambda t: t.id):
        day_keys.setdefault(_norm(ts.day_of_week), ts.day_of_week)
    ordered = sorted(day_keys, key=lambda k: (_day_order(k) is None, _day_order(k) or 0))
    day_idx = {k: i for i, k in enumerate(ordered)}

    slot_pos = {ts.id: (day_idx[_norm(ts.day_of_week)], ts.lesson_number) for ts in raw.timeslots}
    lesson_time: dict[int, str] = {}
    for ts in sorted(raw.timeslots, key=lambda t: t.id):
        lesson_time.setdefault(ts.lesson_number, f"{_fmt_time(ts.start_time)}–{_fmt_time(ts.end_time)}")

    cells: dict[tuple[int, int], list[dict]] = {}
    for r in rows:
        if r[key] != entity_id or r["timeslot_id"] not in slot_pos:
            continue
        d, n = slot_pos[r["timeslot_id"]]
        cell = {"subject": names["subject"].get(r["subject_id"], "?")}
        # во второй строке — то, чего нет в заголовке выбранного вида
        if view != "group":
            cell["group"] = names["group"].get(r["group_id"], "?")
        if view != "teacher":
            cell["teacher"] = names["teacher"].get(r["teacher_id"], "?")
        if view != "classroom":
            cell["classroom"] = names["classroom"].get(r["classroom_id"], "?")
        cells.setdefault((d, n), []).append(cell)

    lessons = [{
        "number": n, "time": lesson_time[n],
        "cells": [cells.get((d, n), []) for d in range(len(ordered))],
    } for n in sorted(lesson_time)]
    return {"days": [day_keys[k] for k in ordered], "lessons": lessons,
            "total": sum(len(v) for v in cells.values())}
