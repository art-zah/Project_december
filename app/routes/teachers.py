import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Teachers, Schedules, TeacherSubjects, TeacherConstraints
from app.templates_config import templates
from app.pedant import Teacher


router = APIRouter(prefix="/teachers")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_teacher(full_name: str, phone: str, max_lessons_per_day: str):
    """Проверяет данные преподавателя."""
    full_name = full_name.strip()
    phone = phone.strip() or None
    return Teacher(full_name=full_name, phone=phone, max_lessons_per_day=max_lessons_per_day)


def get_teacher(db_session, teacher_id: int, user_id: int):
    """Возвращает преподавателя только текущего пользователя."""
    return db_session.execute(select(Teachers).where(Teachers.id == teacher_id, Teachers.user_id == user_id)).scalars().first()


def get_teachers(db_session, user_id: int):
    """Возвращает список преподавателей текущего пользователя."""
    return db_session.execute(select(Teachers).where(Teachers.user_id == user_id).order_by(Teachers.id)).scalars().all()


def teacher_form_response(request: Request, template_name: str, errors: list, full_name: str = "", phone: str = "", 
    max_lessons_per_day: str = "4", teacher=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""
    context = {"request": request, "errors": errors, "full_name": full_name, "phone": phone, "max_lessons_per_day": max_lessons_per_day}

    if teacher is not None:
        context["teacher"] = teacher

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def teacher_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []

    for error in e.errors():
        field = error["loc"][0]

        if field == "full_name":
            errors.append("ФИО обязательно и не должно превышать 255 символов.")
        elif field == "phone":
            errors.append("Номер телефона не должен превышать 20 символов.")
        elif field == "max_lessons_per_day":
            errors.append("Максимальное количество пар в день должно быть положительным целым числом.")

    return errors


# ============================================================
# READ: список преподавателей
# ============================================================

@router.get("/transition", name="transition_to_teachers", tags=["teachers"])
async def transition_to_teachers(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teachers = get_teachers(db_session, user_id)

            # Подготавливаем данные для шаблона, где используется full_name.
            teachers_data = [{"id": teacher.id, "full_name": teacher.name, "phone": teacher.phone, 
                "max_lessons_per_day": teacher.max_lessons_per_day} for teacher in teachers]

        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": teachers_data, "errors": []})

    except SQLAlchemyError:
        logging.exception("Ошибка получения списка преподавателей")
        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": [], "errors": ["Не удалось загрузить список преподавателей."]}, status_code=500)


# ============================================================
# CREATE: форма добавления преподавателя
# ============================================================

@router.get("/create", name="teachers.create", tags=["teachers"])
async def create_teacher_page(request: Request):
    if get_user_id(request) is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(request=request, name="teachers/create_teacher.html", 
        context={"request": request, "errors": [], "full_name": "", "phone": "", "max_lessons_per_day": "4"})


# ============================================================
# CREATE: сохранение преподавателя
# ============================================================

@router.post("/create", name="teachers.create_submit", tags=["teachers"])
async def create_teacher(request: Request, full_name: str = Form(""), phone: str = Form(""), max_lessons_per_day: str = Form("4")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_teacher(full_name, phone, max_lessons_per_day)

        with session() as db_session:
            teacher = Teachers(user_id=user_id, name=data.full_name, phone=data.phone, max_lessons_per_day=data.max_lessons_per_day)
            db_session.add(teacher)
            db_session.commit()

        request.session["flash_success"] = "Преподаватель успешно добавлен."
        return RedirectResponse(url="/teachers/create", status_code=303)

    except ValidationError as e:
        errors = teacher_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Не удалось добавить преподавателя из-за ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания преподавателя")
        errors = ["Не удалось сохранить преподавателя. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: teachers.py/create")
        print("Ошибка в teachers.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500
    return teacher_form_response(request=request, template_name="teachers/create_teacher.html", 
        errors=errors, full_name=full_name, phone=phone, max_lessons_per_day=max_lessons_per_day, status_code=status_code)


# ============================================================
# UPDATE: форма редактирования преподавателя
# ============================================================

@router.get("/update/{id}", name="teachers.edit", tags=["teachers"])
async def edit_teacher_page(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teacher = get_teacher(db_session, id, user_id)

            if teacher is None:
                teachers = get_teachers(db_session, user_id)
                teachers_data = [{"id": item.id, "full_name": item.name, "phone": item.phone, 
                    "max_lessons_per_day": item.max_lessons_per_day} for item in teachers]
                return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
                    context={"request": request, "teachers": teachers_data, "errors": ["Преподаватель не найден."]}, status_code=404)

            teacher_data = {"id": teacher.id, "full_name": teacher.name, "phone": teacher.phone or "", 
                "max_lessons_per_day": teacher.max_lessons_per_day}

        return templates.TemplateResponse(request=request, name="teachers/edit_teacher.html", 
            context={"request": request, "teacher": teacher_data, "errors": []})

    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования преподавателя")
        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": [], "errors": ["Не удалось загрузить данные преподавателя."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений преподавателя
# ============================================================

@router.post("/update/{id}", name="teachers.edit_submit", tags=["teachers"])
async def edit_teacher(request: Request, id: int, full_name: str = Form(""), phone: str = Form(""), max_lessons_per_day: str = Form("4")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_teacher(full_name, phone, max_lessons_per_day)

        with session() as db_session:
            teacher = get_teacher(db_session, id, user_id)

            if teacher is None:
                teachers = get_teachers(db_session, user_id)
                teachers_data = [{"id": item.id, "full_name": item.name, "phone": item.phone, 
                    "max_lessons_per_day": item.max_lessons_per_day} for item in teachers]
                return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
                    context={"request": request, "teachers": teachers_data, "errors": ["Преподаватель не найден."]}, status_code=404)

            teacher.name = data.full_name
            teacher.phone = data.phone
            teacher.max_lessons_per_day = data.max_lessons_per_day
            db_session.commit()

        request.session["flash_success"] = "Данные преподавателя обновлены."
        return RedirectResponse(url="/teachers/transition", status_code=303)

    except ValidationError as e:
        errors = teacher_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Не удалось обновить преподавателя из-за ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования преподавателя")
        errors = ["Не удалось обновить данные преподавателя. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: teachers.py/edit")
        print("Ошибка в teachers.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    # После ошибки заново проверяем принадлежность записи пользователю.
    try:
        with session() as db_session:
            teacher = get_teacher(db_session, id, user_id)

            if teacher is None:
                teachers = get_teachers(db_session, user_id)
                teachers_data = [{"id": item.id, "full_name": item.name, "phone": item.phone, 
                    "max_lessons_per_day": item.max_lessons_per_day} for item in teachers]
                return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
                    context={"request": request, "teachers": teachers_data, "errors": ["Преподаватель не найден."]}, status_code=404)

            teacher_data = {"id": teacher.id, "full_name": full_name, "phone": phone, "max_lessons_per_day": max_lessons_per_day}

        return teacher_form_response(request=request, template_name="teachers/edit_teacher.html", errors=errors, 
            full_name=full_name, phone=phone, max_lessons_per_day=max_lessons_per_day, teacher=teacher_data, status_code=status_code)

    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы преподавателя")
        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": [], "errors": ["Не удалось загрузить данные преподавателя."]}, status_code=500)


# ============================================================
# DELETE: удаление преподавателя
# ============================================================

@router.post("/delete/{id}", name="teachers.delete", tags=["teachers"])
async def delete_teacher(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teacher = get_teacher(db_session, id, user_id)

            if teacher is None:
                teachers = get_teachers(db_session, user_id)
                teachers_data = [{"id": item.id, "full_name": item.name, "phone": item.phone, 
                    "max_lessons_per_day": item.max_lessons_per_day} for item in teachers]
                return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
                    context={"request": request, "teachers": teachers_data, "errors": ["Преподаватель не найден."]}, status_code=404)

            schedule_exists = db_session.execute(select(Schedules.id).where(Schedules.teacher_id == id, Schedules.user_id == user_id).limit(1)).first()
            subject_exists = db_session.execute(select(TeacherSubjects.id)
                .where(TeacherSubjects.teacher_id == id, TeacherSubjects.user_id == user_id).limit(1)).first()
            constraint_exists = db_session.execute(select(TeacherConstraints.id)
                .where(TeacherConstraints.teacher_id == id, TeacherConstraints.user_id == user_id).limit(1)).first()

            if schedule_exists or subject_exists or constraint_exists:
                teachers = get_teachers(db_session, user_id)
                teachers_data = [{"id": item.id, "full_name": item.name, "phone": item.phone, 
                    "max_lessons_per_day": item.max_lessons_per_day} for item in teachers]
                return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
                    context={"request": request, "teachers": teachers_data, 
                        "errors": ["Нельзя удалить преподавателя: он используется в расписании, предметах преподавателей или ограничениях. Сначала удалите или измените связанные записи."]}, 
                        status_code=409)

            db_session.delete(teacher)
            db_session.commit()

        request.session["flash_success"] = "Преподаватель успешно удалён."
        return RedirectResponse(url="/teachers/transition", status_code=303)

    except IntegrityError:
        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": [], "errors": ["Преподавателя нельзя удалить, поскольку на него ссылаются другие записи."]}, 
            status_code=409)

    except SQLAlchemyError:
        logging.exception("Ошибка удаления преподавателя")
        return templates.TemplateResponse(request=request, name="teachers/teachers.html", 
            context={"request": request, "teachers": [], "errors": ["Не удалось удалить преподавателя."]}, status_code=500)
