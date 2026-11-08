import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, TeacherConstraints, Teachers, Timeslots
from app.templates_config import templates
from app.pedant import Constraint


router = APIRouter(prefix="/constraints")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_constraint(teacher_id: str, timeslot_id: str, constraint_type: str):
    """Проверяет данные ограничения."""
    constraint_type = constraint_type.strip()
    return Constraint(teacher_id=teacher_id, timeslot_id=timeslot_id, constraint_type=constraint_type)


def get_constraint(db_session, constraint_id: int, user_id: int):
    """Возвращает ограничение только текущего пользователя."""
    return db_session.execute(select(TeacherConstraints).where(TeacherConstraints.id == constraint_id, 
        TeacherConstraints.user_id == user_id)).scalars().first()


def get_constraints(db_session, user_id: int):
    """Возвращает ограничения текущего пользователя вместе с преподавателями и слотами."""

    result = db_session.execute(select(TeacherConstraints, Teachers, Timeslots).join(Teachers, (Teachers.id == TeacherConstraints.teacher_id) & 
        (Teachers.user_id == TeacherConstraints.user_id)).join(Timeslots, (Timeslots.id == TeacherConstraints.timeslot_id) & 
        (Timeslots.user_id == TeacherConstraints.user_id)).where(TeacherConstraints.user_id == user_id).order_by(TeacherConstraints.id)).all()
    return [{"id": constraint.id, "teacher": {"full_name": teacher.name}, "timeslot": {"day_of_week": timeslot.day_of_week, 
        "lesson_number": timeslot.lesson_number}, "constraint_type": constraint.constraint_type} for constraint, teacher, timeslot in result]


def get_teachers(db_session, user_id: int):
    """Возвращает преподавателей текущего пользователя."""
    teachers = db_session.execute(select(Teachers).where(Teachers.user_id == user_id).order_by(Teachers.name)).scalars().all()
    return [{"id": teacher.id, "full_name": teacher.name} for teacher in teachers]


def get_timeslots(db_session, user_id: int):
    """Возвращает временные слоты текущего пользователя."""
    timeslots = db_session.execute(select(Timeslots).where(Timeslots.user_id == user_id).order_by(Timeslots.id)).scalars().all()
    return [{"id": slot.id, "day_of_week": slot.day_of_week, "lesson_number": slot.lesson_number} for slot in timeslots]


def constraint_form_response(request: Request, template_name: str, errors: list, teachers: list, timeslots: list, teacher_id: str = "", 
        timeslot_id: str = "", constraint_type: str = "Недоступен", constraint=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""

    context = {"request": request, "errors": errors, "teachers": teachers, "timeslots": timeslots, "teacher_id": teacher_id, 
        "timeslot_id": timeslot_id, "constraint_type": constraint_type}
    
    if constraint is not None:
        context["constraint"] = constraint

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def constraint_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []
    for error in e.errors():
        field = error["loc"][0]
        if field == "teacher_id":
            errors.append("Необходимо выбрать преподавателя.")
        elif field == "timeslot_id":
            errors.append("Необходимо выбрать временной слот.")
        elif field == "constraint_type":
            errors.append("Тип ограничения обязателен и не должен превышать 50 символов.")
    return errors


def check_constraint_relations(db_session, teacher_id: int, timeslot_id: int, user_id: int):
    """Проверяет, что преподаватель и временной слот принадлежат пользователю."""
    teacher = db_session.execute(select(Teachers.id).where(Teachers.id == teacher_id, Teachers.user_id == user_id)).first()
    timeslot = db_session.execute(select(Timeslots.id).where(Timeslots.id == timeslot_id, Timeslots.user_id == user_id)).first()
    return teacher is not None and timeslot is not None


# ============================================================
# READ: список ограничений
# ============================================================

@router.get("/transition", name="transition_to_constraints", tags=["constraints"])
async def transition_to_constraints(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            constraints = get_constraints(db_session, user_id)
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": constraints, "errors": []})
    
    except SQLAlchemyError:
        logging.exception("Ошибка получения списка ограничений")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": [], "errors": ["Не удалось загрузить список ограничений."]}, status_code=500)


# ============================================================
# CREATE: форма добавления ограничения
# ============================================================

@router.get("/create", name="constraint.create", tags=["constraints"])
async def create_constraint_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teachers = get_teachers(db_session, user_id)
            timeslots = get_timeslots(db_session, user_id)
        return constraint_form_response(request=request, template_name="constraints/create_constraints.html", 
            errors=[], teachers=teachers, timeslots=timeslots)
    
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы создания ограничения")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": [], "errors": ["Не удалось загрузить данные для формы."]}, status_code=500)


# ============================================================
# CREATE: сохранение ограничения
# ============================================================

@router.post("/create", name="constraint.create_submit", tags=["constraints"])
async def create_constraint(request: Request, teacher_id: str = Form(""), timeslot_id: str = Form(""), constraint_type: str = Form("Недоступен")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_constraint(teacher_id, timeslot_id, constraint_type)

        with session() as db_session:
            if not check_constraint_relations(db_session, data.teacher_id, data.timeslot_id, user_id):
                teachers = get_teachers(db_session, user_id)
                timeslots = get_timeslots(db_session, user_id)
                return constraint_form_response(request=request, template_name="constraints/create_constraints.html", 
                    errors=["Выбранный преподаватель или временной слот не найден."], teachers=teachers, timeslots=timeslots, 
                    teacher_id=teacher_id, timeslot_id=timeslot_id, constraint_type=constraint_type, status_code=400)

            constraint = TeacherConstraints(user_id=user_id, teacher_id=data.teacher_id, timeslot_id=data.timeslot_id, 
                constraint_type=data.constraint_type)
            db_session.add(constraint)
            db_session.commit()

        request.session["flash_success"] = "Ограничение успешно добавлено."
        return RedirectResponse(url="/constraints/transition", status_code=303)

    except ValidationError as e:
        errors = constraint_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Такое ограничение для выбранного преподавателя и слота уже существует."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания ограничения")
        errors = ["Не удалось сохранить ограничение. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.exception(f"{e}, file: constraints.py/create")
        print("Ошибка в constraints.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            teachers = get_teachers(db_session, user_id)
            timeslots = get_timeslots(db_session, user_id)
        return constraint_form_response(request=request, template_name="constraints/create_constraints.html", errors=errors, 
            teachers=teachers, timeslots=timeslots, teacher_id=teacher_id, timeslot_id=timeslot_id, constraint_type=constraint_type, 
            status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы ограничения")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": [], "errors": ["Не удалось загрузить данные формы."]}, status_code=500)


# ============================================================
# UPDATE: форма редактирования ограничения
# ============================================================

@router.get("/update/{id}", name="constraint.edit", tags=["constraints"])
async def edit_constraint_page(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            constraint = get_constraint(db_session, id, user_id)
            if constraint is None:
                return RedirectResponse(url="/constraints/transition", status_code=303)

            teachers = get_teachers(db_session, user_id)
            timeslots = get_timeslots(db_session, user_id)
            constraint_data = {"id": constraint.id, "teacher_id": constraint.teacher_id, "timeslot_id": constraint.timeslot_id, 
                "constraint_type": constraint.constraint_type}

        return constraint_form_response(request=request, template_name="constraints/edit_constraints.html", errors=[], 
            teachers=teachers, timeslots=timeslots, teacher_id=str(constraint_data["teacher_id"]), 
            timeslot_id=str(constraint_data["timeslot_id"]), constraint_type=constraint_data["constraint_type"], constraint=constraint_data)

    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования ограничения")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": [], "errors": ["Не удалось загрузить данные ограничения."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений ограничения
# ============================================================

@router.post("/update/{id}", name="constraint.edit_submit", tags=["constraints"])
async def edit_constraint(request: Request, id: int, teacher_id: str = Form(""), timeslot_id: str = Form(""), constraint_type: str = Form("Недоступен")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_constraint(teacher_id, timeslot_id, constraint_type)

        with session() as db_session:
            constraint = get_constraint(db_session, id, user_id)
            if constraint is None:
                return RedirectResponse(url="/constraints/transition", status_code=303)

            if not check_constraint_relations(db_session, data.teacher_id, data.timeslot_id, user_id):
                teachers = get_teachers(db_session, user_id)
                timeslots = get_timeslots(db_session, user_id)
                constraint_data = {"id": constraint.id, "teacher_id": constraint.teacher_id, "timeslot_id": 
                    constraint.timeslot_id, "constraint_type": constraint.constraint_type}
                return constraint_form_response(request=request, template_name="constraints/edit_constraints.html", 
                    errors=["Выбранный преподаватель или временной слот не найден."], teachers=teachers, timeslots=timeslots, 
                    teacher_id=teacher_id, timeslot_id=timeslot_id, constraint_type=constraint_type, constraint=constraint_data, status_code=400)

            constraint.teacher_id = data.teacher_id
            constraint.timeslot_id = data.timeslot_id
            constraint.constraint_type = data.constraint_type
            db_session.commit()

        request.session["flash_success"] = "Ограничение успешно обновлено."
        return RedirectResponse(url="/constraints/transition", status_code=303)

    except ValidationError as e:
        errors = constraint_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Такое ограничение для выбранного преподавателя и слота уже существует."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования ограничения")
        errors = ["Не удалось обновить ограничение. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: constraints.py/edit")
        print("Ошибка в constraints.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            constraint = get_constraint(db_session, id, user_id)
            if constraint is None:
                return RedirectResponse(url="/constraints/transition", status_code=303)

            teachers = get_teachers(db_session, user_id)
            timeslots = get_timeslots(db_session, user_id)
            constraint_data = {"id": constraint.id, "teacher_id": constraint.teacher_id, "timeslot_id": constraint.timeslot_id, 
                "constraint_type": constraint_type}

        return constraint_form_response(request=request, template_name="constraints/edit_constraints.html", errors=errors, 
            teachers=teachers, timeslots=timeslots, teacher_id=teacher_id, timeslot_id=timeslot_id, constraint_type=constraint_type, 
            constraint=constraint_data, status_code=status_code)

    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы ограничения")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", context={"request": request, 
            "constraints": [], "errors": ["Не удалось загрузить данные ограничения."]}, status_code=500)


# ============================================================
# DELETE: удаление ограничения
# ============================================================

@router.post("/delete/{id}", name="constraint.delete", tags=["constraints"])
async def delete_constraint(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            constraint = get_constraint(db_session, id, user_id)
            if constraint is None:
                return RedirectResponse(url="/constraints/transition", status_code=303)

            db_session.delete(constraint)
            db_session.commit()

        request.session["flash_success"] = "Ограничение успешно удалено."
        return RedirectResponse(url="/constraints/transition", status_code=303)

    except IntegrityError:
        logging.exception("Ошибка ограничения при удалении")
        errors = ["Не удалось удалить ограничение из-за связанных записей."]
        status_code = 409

    except SQLAlchemyError:
        logging.exception("Ошибка удаления ограничения")
        errors = ["Не удалось удалить ограничение. Попробуйте позже."]
        status_code = 500

    try:
        with session() as db_session:
            constraints = get_constraints(db_session, user_id)
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": constraints, "errors": errors}, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки списка ограничений")
        return templates.TemplateResponse(request=request, name="constraints/constraints.html", 
            context={"request": request, "constraints": [], "errors": ["Не удалось загрузить список ограничений."]}, status_code=500)
