"""Единственное место, где модуль общается с БД: чтение данных пользователя и запись расписания.

Все запросы фильтруются по user_id — пользователь видит и меняет только свои данные.
Импорты app.database — внутри функций, чтобы ядро (решатель) можно было импортировать без БД."""
from __future__ import annotations

from .models import (
    RawData, RawClassroom, RawSubject, RawTeacher, RawGroup, RawTimeslot,
    RawTeacherSubject, RawTeacherConstraint, RawLimit,
)


def load_raw_data(db, user_id: int) -> RawData:
    from sqlalchemy import select
    from app.database import (
        Classrooms, Subjects, Teachers, Groups, Timeslots,
        TeacherSubjects, TeacherConstraints, GroupSubjectLimits,
    )

    def rows(model):
        return db.scalars(select(model).where(model.user_id == user_id)).all()

    return RawData(
        classrooms=[RawClassroom(r.id, r.room_number, r.capacity, r.room_type) for r in rows(Classrooms)],
        subjects=[RawSubject(r.id, r.name, r.room_type) for r in rows(Subjects)],
        teachers=[RawTeacher(r.id, r.name, r.max_lessons_per_day) for r in rows(Teachers)],
        groups=[RawGroup(r.id, r.name, r.course) for r in rows(Groups)],
        timeslots=[RawTimeslot(r.id, r.day_of_week, r.lesson_number, r.start_time, r.end_time)
                   for r in rows(Timeslots)],
        teacher_subjects=[RawTeacherSubject(r.teacher_id, r.subject_id) for r in rows(TeacherSubjects)],
        teacher_constraints=[RawTeacherConstraint(r.timeslot_id, r.teacher_id, r.constraint_type)
                             for r in rows(TeacherConstraints)],
        limits=[RawLimit(r.group_id, r.subject_id, getattr(r, "lessons_per_week", getattr(r, "max_lessons_per_week", 0))) for r in rows(GroupSubjectLimits)],
    )


def save_schedule(db, user_id: int, rows: list[dict], replace_existing: bool = True) -> None:
    """Записывает расписание. Старое расписание пользователя удаляется в той же транзакции:
    если вставка упадёт, откат вернёт прежнее расписание. commit делает вызывающий код."""
    from sqlalchemy import delete, insert
    from app.database import Schedules

    if replace_existing:
        db.execute(delete(Schedules).where(Schedules.user_id == user_id))
        db.flush()
    if rows:
        db.execute(insert(Schedules), [{**r, "user_id": user_id} for r in rows])


def load_schedule_rows(db, user_id: int) -> list[dict]:
    """Готовое расписание пользователя (строки таблицы schedules) для показа на сайте."""
    from sqlalchemy import select
    from app.database import Schedules

    rows = db.scalars(select(Schedules).where(Schedules.user_id == user_id)).all()
    return [{"group_id": r.group_id, "subject_id": r.subject_id, "teacher_id": r.teacher_id,
             "classroom_id": r.classroom_id, "timeslot_id": r.timeslot_id} for r in rows]
