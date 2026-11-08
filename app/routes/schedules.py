import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Schedules, Groups, Subjects, Teachers, Classrooms, Timeslots
from app.templates_config import templates
from app.pedant import Schedule


router = APIRouter(prefix="/schedules")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_schedule(group_id: str, subject_id: str, teacher_id: str, classroom_id: str, timeslot_id: str):
    """Проверяет данные записи расписания."""
    return Schedule(group_id=group_id, subject_id=subject_id, teacher_id=teacher_id, classroom_id=classroom_id, timeslot_id=timeslot_id)


def get_schedule(db_session, schedule_id: int, user_id: int):
    """Возвращает запись расписания только текущего пользователя."""
    return db_session.execute(select(Schedules).where(Schedules.id == schedule_id, Schedules.user_id == user_id)).scalars().first()


def get_grouped_schedules(db_session, user_id: int):
    """Возвращает расписание текущего пользователя, сгруппированное по названию группы."""
    stmt = (
        select(Schedules, Groups, Subjects, Teachers, Classrooms, Timeslots)
        .join(Groups, (Groups.id == Schedules.group_id) & (Groups.user_id == Schedules.user_id))
        .join(Subjects, (Subjects.id == Schedules.subject_id) & (Subjects.user_id == Schedules.user_id))
        .join(Teachers, (Teachers.id == Schedules.teacher_id) & (Teachers.user_id == Schedules.user_id))
        .join(Classrooms, (Classrooms.id == Schedules.classroom_id) & (Classrooms.user_id == Schedules.user_id))
        .join(Timeslots, (Timeslots.id == Schedules.timeslot_id) & (Timeslots.user_id == Schedules.user_id))
        .where(Schedules.user_id == user_id)
        .order_by(Groups.name, Timeslots.day_of_week, Timeslots.lesson_number, Schedules.id)
    )
    result = db_session.execute(stmt).all()
    grouped = {}
    for sch, grp, subj, tch, cls, ts in result:
        lesson = {
            "id": sch.id,
            "group": {"id": grp.id, "name": grp.name},
            "subject": {"id": subj.id, "name": subj.name},
            "teacher": {"id": tch.id, "full_name": tch.name},
            "classroom": {"id": cls.id, "room_number": cls.room_number},
            "timeslot": {"id": ts.id, "day_of_week": ts.day_of_week, "lesson_number": ts.lesson_number},
        }
        grouped.setdefault(grp.name, []).append(lesson)
    return grouped

def get_schedule_form_relations(db_session, user_id: int):
    """Возвращает списки сущностей для заполнения выпадающих списков формы расписания."""

    subjects = db_session.execute(select(Subjects).where(Subjects.user_id == user_id).order_by(Subjects.name)).scalars().all()
    teachers = db_session.execute(select(Teachers).where(Teachers.user_id == user_id).order_by(Teachers.name)).scalars().all()
    classrooms = db_session.execute(select(Classrooms).where(Classrooms.user_id == user_id).order_by(Classrooms.room_number)).scalars().all()
    timeslots = db_session.execute(select(Timeslots)
        .where(Timeslots.user_id == user_id).order_by(Timeslots.day_of_week, Timeslots.lesson_number)).scalars().all()

    return (subjects, teachers, classrooms, timeslots)


def schedule_form_response(request: Request, template_name: str, errors: list, group: dict, subjects: list, teachers: list, classrooms: list, 
    timeslots: list, subject_id: str = "", teacher_id: str = "", classroom_id: str = "", timeslot_id: str = "", lesson=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""
    context = {"request": request, "errors": errors, "group": group, "subjects": subjects, "teachers": teachers, "classrooms": classrooms,
        "timeslots": timeslots, "subject_id": subject_id, "teacher_id": teacher_id, "classroom_id": classroom_id, "timeslot_id": timeslot_id}
    
    if lesson is not None:
        context["lesson"] = lesson

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def schedule_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []
    for error in e.errors():
        field = error["loc"][0]
        if field == "group_id":
            errors.append("Необходимо выбрать учебную группу.")
        elif field == "subject_id":
            errors.append("Необходимо выбрать предмет.")
        elif field == "teacher_id":
            errors.append("Необходимо выбрать преподавателя.")
        elif field == "classroom_id":
            errors.append("Необходимо выбрать аудиторию.")
        elif field == "timeslot_id":
            errors.append("Необходимо выбрать временной слот.")
    return errors


def check_schedule_relations(db_session, group_id: int, subject_id: int, teacher_id: int, classroom_id: int, timeslot_id: int, user_id: int):
    """Проверяет, что все связанные сущности существуют и принадлежат текущему пользователю."""
    group = db_session.execute(select(Groups.id).where(Groups.id == group_id, Groups.user_id == user_id)).first()
    subject = db_session.execute(select(Subjects.id).where(Subjects.id == subject_id, Subjects.user_id == user_id)).first()
    teacher = db_session.execute(select(Teachers.id).where(Teachers.id == teacher_id, Teachers.user_id == user_id)).first()
    classroom = db_session.execute(select(Classrooms.id).where(Classrooms.id == classroom_id, Classrooms.user_id == user_id)).first()
    timeslot = db_session.execute(select(Timeslots.id).where(Timeslots.id == timeslot_id, Timeslots.user_id == user_id)).first()
    return all([group, subject, teacher, classroom, timeslot])


# ============================================================
# READ: список занятий расписания
# ============================================================

@router.get("/transition", name="transition_to_schedules", tags=["schedules"])
async def transition_to_schedules(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            grouped_schedules = get_grouped_schedules(db_session, user_id)
        return templates.TemplateResponse(request=request, name="schedules/schedules.html", 
            context={"request": request, "grouped_schedules": grouped_schedules, "errors": []})
    
    except SQLAlchemyError:
        logging.exception("Ошибка получения расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html",
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить расписание."]}, status_code=500)


# ============================================================
# CREATE: форма добавления занятия в расписание
# ============================================================

@router.get("/create", name="schedules.create", tags=["schedules"])
async def create_schedule_page(request: Request, group_id: int = 0):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            group = db_session.execute(select(Groups).where(Groups.id == group_id, Groups.user_id == user_id)).scalars().first()
            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
            group_data = {"id": group.id, "name": group.name}

        return schedule_form_response(request=request, template_name="schedules/create_schedule.html", errors=[], group=group_data,
            subjects=subjects, teachers=teachers, classrooms=classrooms, timeslots=timeslots)
    
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы создания занятия расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html", 
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить данные для формы"]}, 
            status_code=500)


# ============================================================
# CREATE: сохранение занятия в расписание
# ============================================================

@router.post("/create", name="schedules.create_submit", tags=["schedules"])
async def create_schedule(request: Request, group_id: int = 0, subject_id: str = Form(""), teacher_id: str = Form(""),
    classroom_id: str = Form(""), timeslot_id: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_schedule(str(group_id), subject_id, teacher_id, classroom_id, timeslot_id)
        with session() as db_session:
            group = db_session.execute(select(Groups).where(Groups.id == data.group_id, Groups.user_id == user_id)).scalars().first()
            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            if not check_schedule_relations(db_session, data.group_id, data.subject_id, data.teacher_id, data.classroom_id, data.timeslot_id, user_id):
                subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
                group_data = {"id": group.id, "name": group.name}
                return schedule_form_response(request=request, template_name="schedules/create_schedule.html",
                    errors=["Выбранные данные (предмет, преподаватель, аудитория или слот) не найдены."], group=group_data, subjects=subjects,
                    teachers=teachers, classrooms=classrooms, timeslots=timeslots, subject_id=subject_id, teacher_id=teacher_id,
                    classroom_id=classroom_id, timeslot_id=timeslot_id, status_code=400)

            schedule = Schedules(user_id=user_id, group_id=data.group_id, subject_id=data.subject_id, teacher_id=data.teacher_id, 
                classroom_id=data.classroom_id, timeslot_id=data.timeslot_id)
            db_session.add(schedule)
            db_session.commit()

        request.session["flash_success"] = "Занятие успешно добавлено в расписание."
        return RedirectResponse(url=f"/schedules/create?group_id={group_id}", status_code=303)

    except ValidationError as e:
        errors = schedule_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Конфликт в расписании: выбранная группа, преподаватель или аудитория уже заняты в этот временной слот."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка добавления занятия в расписание")
        errors = ["Не удалось сохранить занятие. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: schedules.py/create")
        print("Ошибка в schedules.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            group = db_session.execute(select(Groups).where(Groups.id == group_id, Groups.user_id == user_id)).scalars().first()

            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)
            
            subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
            group_data = {"id": group.id, "name": group.name}
        return schedule_form_response(request=request, template_name="schedules/create_schedule.html", errors=errors, 
            group=group_data, subjects=subjects, teachers=teachers, classrooms=classrooms, timeslots=timeslots, subject_id=subject_id, 
            teacher_id=teacher_id, classroom_id=classroom_id, timeslot_id=timeslot_id, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы создания занятия расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html", 
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить данные для формы"]}, 
            status_code=500)


# ============================================================
# UPDATE: форма редактирования занятия расписания
# ============================================================

@router.get("/update/{id}", name="schedules.edit", tags=["schedules"])
async def edit_schedule_page(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            schedule = get_schedule(db_session, id, user_id)
            if schedule is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            group = db_session.execute(select(Groups).where(Groups.id == schedule.group_id, Groups.user_id == user_id)).scalars().first()
            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
            lesson_data = {"id": schedule.id, "group": {"id": group.id, "name": group.name}, "group_id": schedule.group_id,
                "subject_id": schedule.subject_id, "teacher_id": schedule.teacher_id, "classroom_id": schedule.classroom_id, 
                "timeslot_id": schedule.timeslot_id}
            
        return schedule_form_response(request=request, template_name="schedules/edit_schedule.html", errors=[], group=lesson_data["group"], 
            subjects=subjects, teachers=teachers, classrooms=classrooms, timeslots=timeslots, subject_id=str(schedule.subject_id),
            teacher_id=str(schedule.teacher_id), classroom_id=str(schedule.classroom_id), timeslot_id=str(schedule.timeslot_id), lesson=lesson_data)
    
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования занятия расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html", 
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить данные для формы"]}, 
            status_code=500)


# ============================================================
# UPDATE: сохранение изменений занятия расписания
# ============================================================

@router.post("/update/{id}", name="schedules.edit_submit", tags=["schedules"])
async def edit_schedule(request: Request, id: int, subject_id: str = Form(""), teacher_id: str = Form(""),
    classroom_id: str = Form(""), timeslot_id: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            schedule = get_schedule(db_session, id, user_id)
            if schedule is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)
            group_id = schedule.group_id

        data = validate_schedule(str(group_id), subject_id, teacher_id, classroom_id, timeslot_id)
        with session() as db_session:
            schedule = get_schedule(db_session, id, user_id)
            if schedule is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            group = db_session.execute(select(Groups).where(Groups.id == data.group_id, Groups.user_id == user_id)).scalars().first()
            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            if not check_schedule_relations(db_session, data.group_id, data.subject_id, data.teacher_id, data.classroom_id, data.timeslot_id, user_id):
                subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
                lesson_data = {"id": schedule.id, "group": {"id": group.id, "name": group.name}, "group_id": data.group_id,
                    "subject_id": data.subject_id, "teacher_id": data.teacher_id, "classroom_id": data.classroom_id, "timeslot_id": data.timeslot_id}
                
                return schedule_form_response(request=request, template_name="schedules/edit_schedule.html",
                    errors=["Выбранные данные (предмет, преподаватель, аудитория или слот) не найдены."], group=lesson_data["group"],
                    subjects=subjects, teachers=teachers, classrooms=classrooms, timeslots=timeslots, subject_id=subject_id,
                    teacher_id=teacher_id, classroom_id=classroom_id, timeslot_id=timeslot_id, lesson=lesson_data, status_code=400)

            schedule.subject_id = data.subject_id
            schedule.teacher_id = data.teacher_id
            schedule.classroom_id = data.classroom_id
            schedule.timeslot_id = data.timeslot_id
            db_session.commit()

        request.session["flash_success"] = "Занятие расписания успешно обновлено."
        return RedirectResponse(url="/schedules/transition", status_code=303)

    except ValidationError as e:
        errors = schedule_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Конфликт в расписании: выбранная группа, преподаватель или аудитория уже заняты в этот временной слот."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования занятия расписания")
        errors = ["Не удалось обновить занятие расписания. Попробуйте позже."]
        status_code = 500
    except Exception:
        logging.exception("Неожиданная ошибка редактирования занятия расписания")
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            schedule = get_schedule(db_session, id, user_id)
            if schedule is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)
            group = db_session.execute(select(Groups).where(Groups.id == schedule.group_id, Groups.user_id == user_id)).scalars().first()
            if group is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)
            subjects, teachers, classrooms, timeslots = get_schedule_form_relations(db_session, user_id)
            lesson_data = {"id": schedule.id, "group": {"id": group.id, "name": group.name}, "group_id": schedule.group_id,
                "subject_id": int(subject_id) if subject_id.isdigit() else schedule.subject_id,
                "teacher_id": int(teacher_id) if teacher_id.isdigit() else schedule.teacher_id,
                "classroom_id": int(classroom_id) if classroom_id.isdigit() else schedule.classroom_id,
                "timeslot_id": int(timeslot_id) if timeslot_id.isdigit() else schedule.timeslot_id}
            
        return schedule_form_response(request=request, template_name="schedules/edit_schedule.html", errors=errors,
            group=lesson_data["group"], subjects=subjects, teachers=teachers, classrooms=classrooms, timeslots=timeslots,
            subject_id=subject_id, teacher_id=teacher_id, classroom_id=classroom_id, timeslot_id=timeslot_id, lesson=lesson_data,
            status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы редактирования занятия расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html", 
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить данные для формы"]}, 
            status_code=500)


# ============================================================
# DELETE: удаление занятия из расписания
# ============================================================

@router.post("/delete/{id}", name="schedules.delete", tags=["schedules"])
async def delete_schedule(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            schedule = get_schedule(db_session, id, user_id)
            if schedule is None:
                return RedirectResponse(url="/schedules/transition", status_code=303)

            db_session.delete(schedule)
            db_session.commit()

        request.session["flash_success"] = "Занятие расписания успешно удалено."
        return RedirectResponse(url="/schedules/transition", status_code=303)

    except SQLAlchemyError:
        logging.exception("Ошибка удаления занятия расписания")
        errors = ["Не удалось удалить занятие расписания. Попробуйте позже."]
        status_code = 500

    try:
        with session() as db_session:
            grouped_schedules = get_grouped_schedules(db_session, user_id)
        return templates.TemplateResponse(request=request, name="schedules/schedules.html",
            context={"request": request, "grouped_schedules": grouped_schedules, "errors": errors}, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки расписания")
        return templates.TemplateResponse(request=request, name="schedules/schedules.html",
            context={"request": request, "grouped_schedules": {}, "errors": ["Не удалось загрузить расписание."]}, status_code=500)

