import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Subjects, Schedules, TeacherSubjects, GroupSubjectLimits
from app.templates_config import templates
from app.pedant import Subject


router = APIRouter(prefix="/subjects")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_subject(name: str, room_type: str):
    """Проверяет данные учебной дисциплины."""
    return Subject(name=name.strip(), room_type=room_type.strip())


def get_subject(db_session, subject_id: int, user_id: int):
    """Возвращает дисциплину только текущего пользователя."""
    return db_session.execute(select(Subjects).where(Subjects.id == subject_id, Subjects.user_id == user_id)).scalars().first()


def get_subjects(db_session, user_id: int):
    """Возвращает список дисциплин текущего пользователя."""
    return db_session.execute(select(Subjects).where(Subjects.user_id == user_id).order_by(Subjects.id)).scalars().all()


def subject_to_dict(subject):
    """Преобразует дисциплину в словарь для шаблона."""
    return {"id": subject.id, "name": subject.name, "room_type": subject.room_type}


def subject_form_response(request: Request, template_name: str, errors: list, name: str = "", room_type: str = "", subject=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""
    context = {"request": request, "errors": errors, "name": name, "room_type": room_type}

    if subject is not None:
        context["subject"] = subject

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def subject_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []

    for error in e.errors():
        field = error["loc"][0]
        if field == "name":
            errors.append("Название дисциплины обязательно и должно содержать не более 255 символов.")
        elif field == "room_type":
            errors.append("Тип аудитории обязателен и должен содержать не более 50 символов.")

    return errors


# ============================================================
# READ: список дисциплин
# ============================================================

@router.get("/transition", name="transition_to_subjects", tags=["subjects"])
async def transition_to_subjects(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            subjects = get_subjects(db_session, user_id)
            subjects_data = [subject_to_dict(subject) for subject in subjects]
        return templates.TemplateResponse(request=request, name="subjects/subjects.html", 
            context={"request": request, "subjects": subjects_data, "errors": []})
    except SQLAlchemyError:
        logging.exception("Ошибка получения списка дисциплин")
        return templates.TemplateResponse(request=request, name="subjects/subjects.html", 
            context={"request": request, "subjects": [], "errors": ["Не удалось загрузить список дисциплин."]}, status_code=500)


# ============================================================
# CREATE: форма добавления дисциплины
# ============================================================

@router.get("/create", name="subjects.create", tags=["subjects"])
async def create_subject_page(request: Request):
    if get_user_id(request) is None:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(request=request, name="subjects/create_subject.html", 
        context={"request": request, "errors": [], "name": "", "room_type": ""})


# ============================================================
# CREATE: сохранение дисциплины
# ============================================================

@router.post("/create", name="subjects.create_submit", tags=["subjects"])
async def create_subject(request: Request, name: str = Form(""), room_type: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_subject(name, room_type)
        with session() as db_session:
            subject = Subjects(user_id=user_id, name=data.name, room_type=data.room_type)
            db_session.add(subject)
            db_session.commit()
        request.session["flash_success"] = "Дисциплина успешно добавлена."
        return RedirectResponse(url="/subjects/create", status_code=303)

    except ValidationError as e:
        errors = subject_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Дисциплина с таким названием уже существует или нарушены ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания дисциплины")
        errors = ["Не удалось сохранить дисциплину. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: subjects.py/create")
        print("Ошибка в subjects.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    return subject_form_response(request, "subjects/create_subject.html", errors, name=name, room_type=room_type, status_code=status_code)


# ============================================================
# UPDATE: форма редактирования дисциплины
# ============================================================

@router.get("/update/{id}", name="subjects.edit", tags=["subjects"])
async def edit_subject_page(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            subject = get_subject(db_session, id, user_id)

            if subject is None:
                return RedirectResponse(url="/subjects/transition", status_code=303)
            
            subject_data = subject_to_dict(subject)
        return templates.TemplateResponse(request=request, name="subjects/edit_subject.html", 
            context={"request": request, "subject": subject_data, "errors": []})
    
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования дисциплины")
        return templates.TemplateResponse(request=request, name="subjects/subjects.html", 
            context={"request": request, "subjects": [], "errors": ["Не удалось загрузить данные дисциплины."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений дисциплины
# ============================================================

@router.post("/update/{id}", name="subjects.edit_submit", tags=["subjects"])
async def edit_subject(request: Request, id: int, name: str = Form(""), room_type: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_subject(name, room_type)

        with session() as db_session:
            subject = get_subject(db_session, id, user_id)

            if subject is None:
                return RedirectResponse(url="/subjects/transition", status_code=303)
            
            subject.name = data.name
            subject.room_type = data.room_type
            db_session.commit()

        request.session["flash_success"] = "Данные дисциплины обновлены."
        return RedirectResponse(url="/subjects/transition", status_code=303)

    except ValidationError as e:
        errors = subject_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Дисциплина с таким названием уже существует или нарушены ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования дисциплины")
        errors = ["Не удалось обновить данные дисциплины. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: subjects.py/edit")
        print("Ошибка в subjects.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    # После ошибки заново проверяем принадлежность записи пользователю
    try:
        with session() as db_session:
            subject = get_subject(db_session, id, user_id)

            if subject is None:
                return RedirectResponse(url="/subjects/transition", status_code=303)

            subject_data = {"id": subject.id, "name": name, "room_type": room_type}

        return subject_form_response(request, "subjects/edit_subject.html", errors, name=name, room_type=room_type, 
            subject=subject_data, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы дисциплины")
        return templates.TemplateResponse(request=request, name="subjects/subjects.html", 
            context={"request": request, "subjects": [], "errors": ["Не удалось загрузить данные дисциплины."]}, status_code=500)


# ============================================================
# DELETE: удаление дисциплины
# ============================================================

@router.post("/delete/{id}", name="subjects.delete", tags=["subjects"])
async def delete_subject(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            subject = get_subject(db_session, id, user_id)

            if subject is None:
                return RedirectResponse(url="/subjects/transition", status_code=303)

            # Проверяем связанные записи: расписание, предметы преподавателей, учебные планы (GroupSubjectLimits)
            schedule_exists = db_session.execute(select(Schedules.id).where(Schedules.subject_id == id, Schedules.user_id == user_id).limit(1)).first()
            teacher_subject_exists = db_session.execute(
                select(TeacherSubjects.id).where(TeacherSubjects.subject_id == id, TeacherSubjects.user_id == user_id).limit(1)).first()
            plan_exists = db_session.execute(
                select(GroupSubjectLimits.id).where(GroupSubjectLimits.subject_id == id, GroupSubjectLimits.user_id == user_id).limit(1)).first()

            if schedule_exists or teacher_subject_exists or plan_exists:
                subjects = get_subjects(db_session, user_id)
                subjects_data = [subject_to_dict(subject) for subject in subjects]
                return templates.TemplateResponse(request=request, name="subjects/subjects.html",
                    context={"request": request, "subjects": subjects_data, 
                        "errors": ["Нельзя удалить дисциплину: она используется в расписании, предметах преподавателей или учебном плане. Сначала удалите или измените связанные записи."]},
                    status_code=409)

            db_session.delete(subject)
            db_session.commit()

        request.session["flash_success"] = "Дисциплина успешно удалена."
        return RedirectResponse(url="/subjects/transition", status_code=303)

    except IntegrityError:
        return templates.TemplateResponse(request=request, name="subjects/subjects.html",
            context={"request": request, "subjects": [], "errors": ["Дисциплину нельзя удалить, поскольку на неё ссылаются другие записи."]},
            status_code=409)

    except SQLAlchemyError:
        logging.exception("Ошибка удаления дисциплины")
        return templates.TemplateResponse(request=request, name="subjects/subjects.html",
            context={"request": request, "subjects": [], "errors": ["Не удалось удалить дисциплину."]}, status_code=500)

