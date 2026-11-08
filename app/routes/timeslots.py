import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Timeslots, Schedules, TeacherConstraints
from app.templates_config import templates
from app.pedant import Timeslot


router = APIRouter(prefix="/timeslots")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_timeslot(day_of_week: str, lesson_number: str, start_time: str, end_time: str):
    """Проверяет данные временного слота."""
    day_of_week = day_of_week.strip()
    data = Timeslot(day_of_week=day_of_week, lesson_number=lesson_number, start_time=start_time, end_time=end_time)

    if data.end_time <= data.start_time:
        raise ValueError("Время окончания должно быть позже времени начала.")

    return data


def get_timeslot(db_session, timeslot_id: int, user_id: int):
    """Возвращает временной слот только текущего пользователя."""
    return db_session.execute(select(Timeslots).where(Timeslots.id == timeslot_id, Timeslots.user_id == user_id)).scalars().first()


def get_timeslots(db_session, user_id: int):
    """Возвращает список временных слотов текущего пользователя."""
    return db_session.execute(select(Timeslots).where(Timeslots.user_id == user_id).order_by(Timeslots.id)).scalars().all()


def timeslot_form_response(request: Request, template_name: str, errors: list, day_of_week: str = "", lesson_number: str = "", 
        start_time: str = "", end_time: str = "", timeslot=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""
    context = {"request": request, "errors": errors, "day_of_week": day_of_week, "lesson_number": lesson_number, 
        "start_time": start_time, "end_time": end_time}

    if timeslot is not None:
        context["timeslot"] = timeslot

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def timeslot_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []

    for error in e.errors():
        field = error["loc"][0]

        if field == "day_of_week":
            errors.append("День недели обязателен и не должен превышать 20 символов.")
        elif field == "lesson_number":
            errors.append("Номер пары должен быть положительным целым числом.")
        elif field == "start_time":
            errors.append("Укажите корректное время начала.")
        elif field == "end_time":
            errors.append("Укажите корректное время окончания.")

    return errors


def timeslot_to_dict(timeslot):
    """Преобразует временной слот в словарь для шаблона."""
    return {"id": timeslot.id, "day_of_week": timeslot.day_of_week, "lesson_number": timeslot.lesson_number, 
        "start_time": timeslot.start_time.strftime("%H:%M"), "end_time": timeslot.end_time.strftime("%H:%M")}

def timeslot_integrity_error(e: IntegrityError):
    """Преобразует ошибки ограничений базы данных в понятные сообщения."""
    if "day_of_week_lesson_number_user_id_time" in str(e.orig):
        return ["Такая пара в этот день недели уже существует."]
    return ["Не удалось сохранить временной слот из-за ограничения базы данных."]

# ============================================================
# READ: список временных слотов
# ============================================================

@router.get("/transition", name="transition_to_timeslots", tags=["timeslots"])
async def transition_to_timeslots(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            timeslots = get_timeslots(db_session, user_id)
            timeslots_data = [timeslot_to_dict(slot) for slot in timeslots]

        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": timeslots_data, "errors": []})

    except SQLAlchemyError:
        logging.exception("Ошибка получения списка временных слотов")
        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": [], "errors": ["Не удалось загрузить список временных слотов."]}, status_code=500)


# ============================================================
# CREATE: форма добавления временного слота
# ============================================================

@router.get("/create", name="timeslots.create", tags=["timeslots"])
async def create_timeslot_page(request: Request):
    if get_user_id(request) is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(request=request, name="timeslots/create_timeslot.html", 
        context={"request": request, "errors": [], "day_of_week": "", "lesson_number": "", "start_time": "", "end_time": ""})


# ============================================================
# CREATE: сохранение временного слота
# ============================================================

@router.post("/create", name="timeslots.create_submit", tags=["timeslots"])
async def create_timeslot(request: Request, day_of_week: str = Form(""), lesson_number: str = Form(""), start_time: str = Form(""), 
    end_time: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_timeslot(day_of_week, lesson_number, start_time, end_time)

        with session() as db_session:
            timeslot = Timeslots(user_id=user_id, day_of_week=data.day_of_week, lesson_number=data.lesson_number, start_time=data.start_time, 
            end_time=data.end_time)

            db_session.add(timeslot)
            db_session.commit()

        request.session["flash_success"] = "Временной слот успешно добавлен."
        return RedirectResponse(url="/timeslots/create", status_code=303)

    except ValidationError as e:
        errors = timeslot_validation_errors(e)
        status_code = 400
    except IntegrityError as e:
        errors = timeslot_integrity_error(e)
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания временного слота")
        errors = ["Не удалось сохранить временной слот. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: timeslots.py/create")
        print("Ошибка в timeslots.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    return timeslot_form_response(request=request, template_name="timeslots/create_timeslot.html", errors=errors, day_of_week=day_of_week, 
        lesson_number=lesson_number, start_time=start_time, end_time=end_time, status_code=status_code)


# ============================================================
# UPDATE: форма редактирования временного слота
# ============================================================

@router.get("/update/{id}", name="timeslots.edit", tags=["timeslots"])
async def edit_timeslot_page(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            timeslot = get_timeslot(db_session, id, user_id)

            if timeslot is None:
                return RedirectResponse(url="/timeslots/transition", status_code=303)

            timeslot_data = timeslot_to_dict(timeslot)

        return templates.TemplateResponse(request=request, name="timeslots/edit_timeslot.html", 
            context={"request": request, "timeslot": timeslot_data, "errors": []})

    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования временного слота")
        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": [], "errors": ["Не удалось загрузить данные временного слота."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений временного слота
# ============================================================

@router.post("/update/{id}", name="timeslots.edit_submit", tags=["timeslots"])
async def edit_timeslot(request: Request, id: int, day_of_week: str = Form(""), lesson_number: str = Form(""), start_time: str = Form(""), 
    end_time: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_timeslot(day_of_week, lesson_number, start_time, end_time)

        with session() as db_session:
            timeslot = get_timeslot(db_session, id, user_id)

            if timeslot is None:
                return RedirectResponse(url="/timeslots/transition", status_code=303)

            timeslot.day_of_week = data.day_of_week
            timeslot.lesson_number = data.lesson_number
            timeslot.start_time = data.start_time
            timeslot.end_time = data.end_time
            db_session.commit()

        request.session["flash_success"] = "Временной слот успешно обновлён."
        return RedirectResponse(url="/timeslots/transition", status_code=303)

    except ValidationError as e:
        errors = timeslot_validation_errors(e)
        status_code = 400
    except IntegrityError as e:
        errors = timeslot_integrity_error(e)
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования временного слота")
        errors = ["Не удалось обновить временной слот. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: timeslots.py/edit")
        print("Ошибка в timeslots.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            timeslot = get_timeslot(db_session, id, user_id)

            if timeslot is None:
                return RedirectResponse(url="/timeslots/transition", status_code=303)

            timeslot_data = {"id": timeslot.id, "day_of_week": day_of_week, "lesson_number": lesson_number, "start_time": start_time, 
                "end_time": end_time}

        return timeslot_form_response(request=request, template_name="timeslots/edit_timeslot.html", errors=errors, day_of_week=day_of_week, 
            lesson_number=lesson_number, start_time=start_time, end_time=end_time, timeslot=timeslot_data, status_code=status_code)

    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы временного слота")
        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": [], "errors": ["Не удалось загрузить данные временного слота."]}, status_code=500)


# ============================================================
# DELETE: удаление временного слота
# ============================================================

@router.post("/delete/{id}", name="timeslots.delete", tags=["timeslots"])
async def delete_timeslot(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            timeslot = get_timeslot(db_session, id, user_id)

            if timeslot is None:
                return RedirectResponse(url="/timeslots/transition", status_code=303)

            schedule_exists = db_session.execute(select(Schedules.id)
                .where(Schedules.timeslot_id == id, Schedules.user_id == user_id).limit(1)).first()
            
            constraint_exists = db_session.execute(select(TeacherConstraints.id)
                .where(TeacherConstraints.timeslot_id == id, TeacherConstraints.user_id == user_id).limit(1)).first()

            if schedule_exists or constraint_exists:
                timeslots = get_timeslots(db_session, user_id)
                timeslots_data = [timeslot_to_dict(slot) for slot in timeslots]
                return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
                    context={"request": request, "timeslots": timeslots_data, 
                    "errors": ["Нельзя удалить слот: он используется в расписании или ограничениях преподавателей. Сначала удалите или измените связанные записи."]}, 
                    status_code=409)

            db_session.delete(timeslot)
            db_session.commit()

        request.session["flash_success"] = "Временной слот успешно удалён."
        return RedirectResponse(url="/timeslots/transition", status_code=303)
    
    except IntegrityError:
        logging.exception("Ошибка ограничения при удалении временного слота")
        errors = ["Временной слот нельзя удалить, поскольку на него ссылаются другие записи."]
        status_code = 409
    except SQLAlchemyError:
        logging.exception("Ошибка удаления временного слота")
        errors = ["Не удалось удалить временной слот. Попробуйте позже."]
        status_code = 500

    try:
        with session() as db_session:
            timeslots = get_timeslots(db_session, user_id)
            timeslots_data = [timeslot_to_dict(slot) for slot in timeslots]
        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": timeslots_data, "errors": errors}, status_code=status_code)

    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки списка временных слотов")
        return templates.TemplateResponse(request=request, name="timeslots/timeslots.html", 
            context={"request": request, "timeslots": [], "errors": ["Не удалось загрузить список временных слотов."]}, status_code=500)
