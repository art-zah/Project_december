"""Простые структуры данных. Здесь нет зависимостей от БД — ядро можно тестировать отдельно."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


# ---- «Сырые» строки из БД (уже отфильтрованные по user_id) -------------------------------
@dataclass(frozen=True, slots=True)
class RawClassroom:
    id: int
    room_number: str
    capacity: int
    room_type: str


@dataclass(frozen=True, slots=True)
class RawSubject:
    id: int
    name: str
    room_type: str


@dataclass(frozen=True, slots=True)
class RawTeacher:
    id: int
    name: str
    max_lessons_per_day: int


@dataclass(frozen=True, slots=True)
class RawGroup:
    id: int
    name: str
    course: int


@dataclass(frozen=True, slots=True)
class RawTimeslot:
    id: int
    day_of_week: str
    lesson_number: int
    start_time: Any
    end_time: Any


@dataclass(frozen=True, slots=True)
class RawTeacherSubject:
    teacher_id: int
    subject_id: int


@dataclass(frozen=True, slots=True)
class RawTeacherConstraint:
    timeslot_id: int
    teacher_id: int
    constraint_type: str


@dataclass(frozen=True, slots=True)
class RawLimit:
    group_id: int
    subject_id: int
    max_lessons_per_week: int


@dataclass(slots=True)
class RawData:
    classrooms: list[RawClassroom] = field(default_factory=list)
    subjects: list[RawSubject] = field(default_factory=list)
    teachers: list[RawTeacher] = field(default_factory=list)
    groups: list[RawGroup] = field(default_factory=list)
    timeslots: list[RawTimeslot] = field(default_factory=list)
    teacher_subjects: list[RawTeacherSubject] = field(default_factory=list)
    teacher_constraints: list[RawTeacherConstraint] = field(default_factory=list)
    limits: list[RawLimit] = field(default_factory=list)


# ---- Индексированная задача для решателя ---------------------------------------------------
@dataclass(frozen=True, slots=True)
class SlotInfo:
    db_id: int
    day: int      # индекс дня 0..n_days-1 (по порядку недели)
    pos: int      # позиция внутри дня 0..k-1 (по порядку пар)
    day_name: str
    lesson_number: int


@dataclass(slots=True)
class Problem:
    user_id: int
    slots: list[SlotInfo]
    n_days: int
    day_slots: list[list[int]]          # day -> [индексы слотов по порядку]
    slot_day: list[int]
    group_ids: list[int]
    group_names: list[str]
    subject_ids: list[int]
    subject_names: list[str]
    teacher_ids: list[int]
    teacher_names: list[str]
    room_ids: list[int]
    room_numbers: list[str]
    max_day: list[int]                  # teacher -> лимит пар в день
    teachers_for_subject: list[list[int]]
    rooms_for_subject: list[list[int]]
    blocked: list[set[int]]             # teacher -> слоты, где нельзя
    preferred: list[set[int]]
    avoid: list[set[int]]
    lesson_g: list[int] = field(default_factory=list)   # номер урока -> группа
    lesson_s: list[int] = field(default_factory=list)   # номер урока -> предмет
    skipped: list[tuple[int, int, str]] = field(default_factory=list)  # (g, s, причина) по одному на урок
    warnings: list[str] = field(default_factory=list)


# ---- Результат -----------------------------------------------------------------------------
@dataclass(slots=True)
class GenerationResult:
    success: bool                     # все запрошенные пары поставлены
    total_lessons: int                # сколько пар требовалось поставить
    placed: int
    unplaced: list[dict] = field(default_factory=list)   # {group_id, group, subject_id, subject, reason}
    warnings: list[str] = field(default_factory=list)
    rows: list[dict] = field(default_factory=list)       # строки для таблицы schedules
    soft_cost: float = 0.0            # качество (меньше — лучше)
    elapsed: float = 0.0
    seed: int | None = None
    saved: bool = False

    def to_dict(self, include_rows: bool = False) -> dict:
        d = asdict(self)
        if not include_rows:
            d.pop("rows")
        return d
