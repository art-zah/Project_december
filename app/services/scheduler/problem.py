"""Превращает «сырые» данные из БД в индексированную задачу (Problem) для решателя.

Здесь же отсеиваются заведомо невыполнимые пары (нет преподавателя / аудитории) —
с понятной причиной, которая потом попадёт в результат.
"""
from __future__ import annotations

from . import config
from .models import RawData, Problem, SlotInfo


def _norm(value) -> str:
    return (str(value) if value is not None else "").strip().casefold()


def _day_order(name: str) -> int | None:
    n = _norm(name)
    for idx, aliases in config.DAY_ALIASES.items():
        if n in aliases:
            return idx
    return None


def build_problem(raw: RawData, user_id: int) -> Problem:
    warnings: list[str] = []

    # ---- слоты: сортируем по дню недели и номеру пары ------------------------------------
    day_names: dict[str, str] = {}          # нормализованное имя -> исходное
    for ts in sorted(raw.timeslots, key=lambda t: t.id):
        day_names.setdefault(_norm(ts.day_of_week), ts.day_of_week)

    known, unknown = [], []
    for key in day_names:
        order = _day_order(key)
        (known if order is not None else unknown).append((order, key))
    if unknown:
        warnings.append(
            "Не распознаны названия дней недели: "
            + ", ".join(day_names[k] for _, k in unknown)
            + ". Они поставлены после известных дней в порядке появления в БД."
        )
    ordered_days = [k for _, k in sorted(known)] + [k for _, k in unknown]
    day_index = {k: i for i, k in enumerate(ordered_days)}
    n_days = len(ordered_days)

    ts_sorted = sorted(
        raw.timeslots,
        key=lambda t: (day_index[_norm(t.day_of_week)], t.lesson_number, str(t.start_time), t.id),
    )
    slots: list[SlotInfo] = []
    day_slots: list[list[int]] = [[] for _ in range(n_days)]
    slot_idx_by_id: dict[int, int] = {}
    for ts in ts_sorted:
        d = day_index[_norm(ts.day_of_week)]
        pos = len(day_slots[d])
        idx = len(slots)
        slots.append(SlotInfo(ts.id, d, pos, ts.day_of_week, ts.lesson_number))
        day_slots[d].append(idx)
        slot_idx_by_id[ts.id] = idx
    slot_day = [s.day for s in slots]

    # ---- справочники ----------------------------------------------------------------------
    group_ids = [g.id for g in raw.groups]
    g_idx = {gid: i for i, gid in enumerate(group_ids)}
    subject_ids = [s.id for s in raw.subjects]
    s_idx = {sid: i for i, sid in enumerate(subject_ids)}
    teacher_ids = [t.id for t in raw.teachers]
    t_idx = {tid: i for i, tid in enumerate(teacher_ids)}
    room_ids = [r.id for r in raw.classrooms]

    max_day = [t.max_lessons_per_day for t in raw.teachers]

    # ---- кто какой предмет ведёт ----------------------------------------------------------
    teachers_for_subject: list[list[int]] = [[] for _ in subject_ids]
    seen = set()
    for ts in raw.teacher_subjects:
        if ts.teacher_id not in t_idx or ts.subject_id not in s_idx:
            continue
        t, s = t_idx[ts.teacher_id], s_idx[ts.subject_id]
        if (t, s) in seen or max_day[t] <= 0:
            continue
        seen.add((t, s))
        teachers_for_subject[s].append(t)

    # ---- аудитории по типу ----------------------------------------------------------------
    rooms_by_type: dict[str, list[int]] = {}
    for i, r in enumerate(raw.classrooms):
        rooms_by_type.setdefault(_norm(r.room_type), []).append(i)
    rooms_for_subject = [rooms_by_type.get(_norm(s.room_type), []) for s in raw.subjects]

    # ---- ограничения преподавателей -------------------------------------------------------
    blocked = [set() for _ in teacher_ids]
    preferred = [set() for _ in teacher_ids]
    avoid = [set() for _ in teacher_ids]
    unknown_types: set[str] = set()
    for c in raw.teacher_constraints:
        if c.teacher_id not in t_idx or c.timeslot_id not in slot_idx_by_id:
            continue
        t, sl = t_idx[c.teacher_id], slot_idx_by_id[c.timeslot_id]
        kind = _norm(c.constraint_type)
        if kind in config.PREFERRED_CONSTRAINT_TYPES:
            preferred[t].add(sl)
        elif kind in config.AVOID_CONSTRAINT_TYPES:
            avoid[t].add(sl)
        else:
            blocked[t].add(sl)
            if kind not in config.HARD_CONSTRAINT_TYPES:
                unknown_types.add(c.constraint_type)
    if unknown_types:
        warnings.append(
            "Неизвестные типы ограничений преподавателей трактованы как «нельзя ставить»: "
            + ", ".join(sorted(unknown_types))
        )

    # ---- «уроки»: по одной единице на каждую пару в неделю --------------------------------
    p = Problem(
        user_id=user_id, slots=slots, n_days=n_days, day_slots=day_slots, slot_day=slot_day,
        group_ids=group_ids, group_names=[g.name for g in raw.groups],
        subject_ids=subject_ids, subject_names=[s.name for s in raw.subjects],
        teacher_ids=teacher_ids, teacher_names=[t.name for t in raw.teachers],
        room_ids=room_ids, room_numbers=[r.room_number for r in raw.classrooms],
        max_day=max_day, teachers_for_subject=teachers_for_subject,
        rooms_for_subject=rooms_for_subject, blocked=blocked, preferred=preferred, avoid=avoid,
        warnings=warnings,
    )

    if not slots:
        warnings.append("В таблице timeslots нет ни одного временного слота — ставить пары некуда.")

    per_group_total = [0] * len(group_ids)
    for lim in sorted(raw.limits, key=lambda x: (x.group_id, x.subject_id)):
        if lim.group_id not in g_idx or lim.subject_id not in s_idx:
            warnings.append(
                f"group_subject_limits: группа {lim.group_id} или предмет {lim.subject_id} не найдены — пропущено."
            )
            continue
        g, s = g_idx[lim.group_id], s_idx[lim.subject_id]
        n = lim.max_lessons_per_week
        if n <= 0:
            continue
        reason = None
        if not slots:
            reason = "нет временных слотов"
        elif not teachers_for_subject[s]:
            reason = "нет преподавателя, который ведёт этот предмет (teacher_subjects)"
        elif not rooms_for_subject[s]:
            reason = f"нет аудитории типа «{raw.subjects[s].room_type}»"
        elif all(len(blocked[t]) >= len(slots) for t in teachers_for_subject[s]):
            reason = "все преподаватели этого предмета недоступны во все слоты"
        for _ in range(n):
            if reason:
                p.skipped.append((g, s, reason))
            else:
                p.lesson_g.append(g)
                p.lesson_s.append(s)
                per_group_total[g] += 1

    for g, total in enumerate(per_group_total):
        if slots and total > len(slots):
            warnings.append(
                f"Группа «{p.group_names[g]}»: требуется {total} пар в неделю, а слотов только {len(slots)} — "
                f"часть пар поставить невозможно."
            )
    return p
