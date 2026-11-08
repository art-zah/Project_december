"""Публичная точка входа модуля: generate_schedule(user_id)."""
from __future__ import annotations

import time

from . import config as C
from .models import GenerationResult
from .problem import build_problem
from .solver import solve
from .verify import verify_rows


class ScheduleGenerationError(RuntimeError):
    """Внутренняя ошибка генератора (например, найдено нарушение жёстких правил)."""


def build_result(raw, user_id: int, time_limit: float = C.DEFAULT_TIME_LIMIT,
                 seed: int | None = None) -> GenerationResult:
    """Чистая функция без БД: сырые данные -> результат. Используется и в тестах."""
    t0 = time.perf_counter()
    p = build_problem(raw, user_id)
    sol = solve(p, time_limit=time_limit, seed=seed)

    rows = [{
        "group_id": p.group_ids[p.lesson_g[l]],
        "subject_id": p.subject_ids[p.lesson_s[l]],
        "teacher_id": p.teacher_ids[t],
        "classroom_id": p.room_ids[r],
        "timeslot_id": p.slots[sl].db_id,
    } for l, sl, t, r in sol.assignments]

    errors = verify_rows(raw, rows)
    if errors:
        raise ScheduleGenerationError("Сгенерированное расписание нарушает правила: " + "; ".join(errors[:5]))

    unplaced = [{
        "group_id": p.group_ids[g], "group": p.group_names[g],
        "subject_id": p.subject_ids[s], "subject": p.subject_names[s], "reason": reason,
    } for g, s, reason in p.skipped]
    unplaced += [{
        "group_id": p.group_ids[p.lesson_g[l]], "group": p.group_names[p.lesson_g[l]],
        "subject_id": p.subject_ids[p.lesson_s[l]], "subject": p.subject_names[p.lesson_s[l]],
        "reason": "не нашлось свободного сочетания время/преподаватель/аудитория (лимит «не более», недобор допустим)",
    } for l in sol.unplaced]

    total = len(p.lesson_g) + len(p.skipped)
    return GenerationResult(
        success=not unplaced and total > 0, total_lessons=total, placed=len(rows),
        unplaced=unplaced, warnings=p.warnings, rows=rows, soft_cost=round(sol.cost, 2),
        elapsed=round(time.perf_counter() - t0, 2), seed=seed,
    )


def generate_schedule(user_id: int, *, time_limit: float = C.DEFAULT_TIME_LIMIT,
                      seed: int | None = None, save: bool = True,
                      replace_existing: bool = True, db_session=None) -> GenerationResult:
    """Генерирует расписание для пользователя user_id и (по умолчанию) записывает его в schedules.

    time_limit        — максимум секунд на генерацию (по умолчанию 8);
    seed              — для воспроизводимости; None — каждый раз новый вариант;
    save=False        — «пробный прогон»: ничего не пишем в БД;
    replace_existing  — удалить прежнее расписание пользователя перед записью;
    db_session        — своя сессия SQLAlchemy; если не передана, создаётся и закрывается внутри.
                        Запись фиксируется (commit) в любом случае.

    Если нечего расставлять (нет групп/лимитов), прежнее расписание НЕ стирается.
    """
    from .db_io import load_raw_data, save_schedule

    own_session = db_session is None
    if own_session:
        from app.database import session as session_factory
        db = session_factory()
    else:
        db = db_session
    try:
        raw = load_raw_data(db, user_id)
        result = build_result(raw, user_id, time_limit=time_limit, seed=seed)
        if save and result.total_lessons > 0:
            save_schedule(db, user_id, result.rows, replace_existing)
            db.commit()
            result.saved = True
        elif result.total_lessons == 0:
            result.warnings.append("Нет данных для генерации (проверьте group_subject_limits) — расписание не менялось.")
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        if own_session:
            db.close()
