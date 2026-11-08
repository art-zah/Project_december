import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, TeacherSubjects, Teachers, Subjects
from app.templates_config import templates
from app.pedant import TeacherSubject


router = APIRouter(prefix="/teacher_subjects")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_teacher_subject(teacher_id: str, subject_id: str):
    """Проверяет данные связи преподавателя и предмета."""
    return TeacherSubject(teacher_id=teacher_id, subject_id=subject_id)


def get_teacher_subject(db_session, item_id: int, user_id: int):
    """Возвращает связь только текущего пользователя."""
    return db_session.execute(select(TeacherSubjects).where(TeacherSubjects.id == item_id, TeacherSubjects.user_id == user_id)).scalars().first()


def get_teacher_subjects(db_session, user_id: int):
    """Возвращает список связей текущего пользователя с преподавателями и предметами."""
    result = db_session.execute(select(TeacherSubjects, Teachers, Subjects)
        .join(Teachers, (Teachers.id == TeacherSubjects.teacher_id) & (Teachers.user_id == TeacherSubjects.user_id))
        .join(Subjects, (Subjects.id == TeacherSubjects.subject_id) & (Subjects.user_id == TeacherSubjects.user_id))
        .where(TeacherSubjects.user_id == user_id).order_by(TeacherSubjects.id)).all()
    return [{"id": ts.id, "teacher_id": ts.teacher_id, "subject_id": ts.subject_id, "teacher": {"full_name": teacher.name}, 
        "subject": {"name": subject.name}} for ts, teacher, subject in result]


def get_teachers(db_session, user_id: int):
    """Возвращает список преподавателей текущего пользователя."""
    teachers = db_session.execute(select(Teachers).where(Teachers.user_id == user_id).order_by(Teachers.name)).scalars().all()
    return [{"id": teacher.id, "full_name": teacher.name} for teacher in teachers]


def get_subjects(db_session, user_id: int):
    """Возвращает список дисциплин текущего пользователя."""
    subjects = db_session.execute(select(Subjects).where(Subjects.user_id == user_id).order_by(Subjects.name)).scalars().all()
    return [{"id": subject.id, "name": subject.name} for subject in subjects]


def teacher_subject_form_response(request: Request, template_name: str, errors: list, teachers: list, subjects: list, teacher_id: str = "", 
        subject_id: str = "", teacher_subject=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""
    context = {"request": request, "errors": errors, "teachers": teachers, "subjects": subjects, "teacher_id": teacher_id, "subject_id": subject_id}
    if teacher_subject is not None:
        context["teacher_subject"] = teacher_subject
    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def teacher_subject_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []
    for error in e.errors():
        field = error["loc"][0]
        if field == "teacher_id":
            errors.append("Необходимо выбрать преподавателя.")
        elif field == "subject_id":
            errors.append("Необходимо выбрать предмет.")
    return errors


def check_teacher_subject_relations(db_session, teacher_id: int, subject_id: int, user_id: int):
    """Проверяет, что преподаватель и предмет принадлежат текущему пользователю."""
    teacher = db_session.execute(select(Teachers.id).where(Teachers.id == teacher_id, Teachers.user_id == user_id)).first()
    subject = db_session.execute(select(Subjects.id).where(Subjects.id == subject_id, Subjects.user_id == user_id)).first()
    return teacher is not None and subject is not None


# ============================================================
# READ: список связей преподавателей и предметов
# ============================================================

@router.get("/transition", name="transition_to_teacher_subjects", tags=["teacher_subjects"])
async def transition_to_teacher_subjects(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teacher_subjects = get_teacher_subjects(db_session, user_id)
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": teacher_subjects, "errors": []})
    except SQLAlchemyError:
        logging.exception("Ошибка получения списка предметов преподавателей")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить список предметов преподавателей."]}, status_code=500)


# ============================================================
# CREATE: форма добавления связи
# ============================================================

@router.get("/create", name="teacher_subjects.create", tags=["teacher_subjects"])
async def create_teacher_subject_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teachers = get_teachers(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
        return teacher_subject_form_response(request, "teacher_subjects/create_teacher_subject.html", errors=[], teachers=teachers, subjects=subjects)
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы создания связи преподавателя и предмета")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить данные для формы."]}, status_code=500)


# ============================================================
# CREATE: сохранение связи
# ============================================================

@router.post("/create", name="teacher_subjects.create_submit", tags=["teacher_subjects"])
async def create_teacher_subject(request: Request, teacher_id: str = Form(""), subject_id: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_teacher_subject(teacher_id, subject_id)
        with session() as db_session:
            if not check_teacher_subject_relations(db_session, data.teacher_id, data.subject_id, user_id):
                teachers = get_teachers(db_session, user_id)
                subjects = get_subjects(db_session, user_id)
                return teacher_subject_form_response(request, "teacher_subjects/create_teacher_subject.html", 
                    errors=["Выбранный преподаватель или предмет не найден."], teachers=teachers, subjects=subjects, teacher_id=teacher_id, 
                    subject_id=subject_id, status_code=400)

            teacher_subject_validate = TeacherSubjects(user_id=user_id, teacher_id=data.teacher_id, subject_id=data.subject_id)
            db_session.add(teacher_subject_validate)
            db_session.commit()

        request.session["flash_success"] = "Связь преподавателя и предмета успешно добавлена."
        return RedirectResponse(url="/teacher_subjects/create", status_code=303)

    except ValidationError as e:
        errors = teacher_subject_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Такая связь между преподавателем и предметом уже существует."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания связи преподавателя и предмета")
        errors = ["Не удалось сохранить связь. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: teacher_subjects.py/create")
        print("Ошибка в teacher_subjects.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            teachers = get_teachers(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
        return teacher_subject_form_response(request, "teacher_subjects/create_teacher_subject.html", errors=errors, teachers=teachers, 
            subjects=subjects, teacher_id=teacher_id, subject_id=subject_id, status_code=status_code)
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы создания связи")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить данные формы."]}, status_code=500)


# ============================================================
# UPDATE: форма редактирования связи
# ============================================================

@router.get("/update/{id}", name="teacher_subjects.edit", tags=["teacher_subjects"])
async def edit_teacher_subject_page(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teacher_subject = get_teacher_subject(db_session, id, user_id)
            if teacher_subject is None:
                return RedirectResponse(url="/teacher_subjects/transition", status_code=303)

            teachers = get_teachers(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
            teacher_subject_data = {"id": teacher_subject.id, "teacher_id": teacher_subject.teacher_id, "subject_id": teacher_subject.subject_id}

        return teacher_subject_form_response(request, "teacher_subjects/edit_teacher_subject.html", errors=[], teachers=teachers, 
            subjects=subjects, teacher_id=str(teacher_subject_data["teacher_id"]), subject_id=str(teacher_subject_data["subject_id"]), 
            teacher_subject=teacher_subject_data)
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования связи")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить данные связи."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений связи
# ============================================================

@router.post("/update/{id}", name="teacher_subjects.edit_submit", tags=["teacher_subjects"])
async def edit_teacher_subject(request: Request, id: int, teacher_id: str = Form(""), subject_id: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_teacher_subject(teacher_id, subject_id)
        with session() as db_session:
            teacher_subject = get_teacher_subject(db_session, id, user_id)
            if teacher_subject is None:
                return RedirectResponse(url="/teacher_subjects/transition", status_code=303)

            if not check_teacher_subject_relations(db_session, data.teacher_id, data.subject_id, user_id):
                teachers = get_teachers(db_session, user_id)
                subjects = get_subjects(db_session, user_id)
                teacher_subject_data = {"id": teacher_subject.id, "teacher_id": teacher_subject.teacher_id, "subject_id": teacher_subject.subject_id}
                return teacher_subject_form_response(request, "teacher_subjects/edit_teacher_subject.html", 
                    errors=["Выбранный преподаватель или предмет не найден."], teachers=teachers, subjects=subjects, teacher_id=teacher_id, 
                    subject_id=subject_id, teacher_subject=teacher_subject_data, status_code=400)

            teacher_subject.teacher_id = data.teacher_id
            teacher_subject.subject_id = data.subject_id
            db_session.commit()

        request.session["flash_success"] = "Связь преподавателя и предмета успешно обновлена."
        return RedirectResponse(url="/teacher_subjects/transition", status_code=303)

    except ValidationError as e:
        errors = teacher_subject_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Такая связь между преподавателем и предметом уже существует."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования связи преподавателя и предмета")
        errors = ["Не удалось обновить связь. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: teacher_subjects.py/edit")
        print("Ошибка в teacher_subjects.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            teacher_subject = get_teacher_subject(db_session, id, user_id)
            if teacher_subject is None:
                return RedirectResponse(url="/teacher_subjects/transition", status_code=303)
            
            teachers = get_teachers(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
            teacher_subject_data = {"id": teacher_subject.id, "teacher_id": teacher_subject.teacher_id, "subject_id": teacher_subject.subject_id}
        return teacher_subject_form_response(request, "teacher_subjects/edit_teacher_subject.html", errors=errors, teachers=teachers, 
            subjects=subjects, teacher_id=teacher_id, subject_id=subject_id, teacher_subject=teacher_subject_data, status_code=status_code)
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы редактирования связи")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить данные связи."]}, status_code=500)


# ============================================================
# DELETE: удаление связи
# ============================================================

@router.post("/delete/{id}", name="teacher_subjects.delete", tags=["teacher_subjects"])
async def delete_teacher_subject(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            teacher_subject = get_teacher_subject(db_session, id, user_id)
            if teacher_subject is None:
                return RedirectResponse(url="/teacher_subjects/transition", status_code=303)

            db_session.delete(teacher_subject)
            db_session.commit()

        request.session["flash_success"] = "Связь преподавателя и предмета успешно удалена."
        return RedirectResponse(url="/teacher_subjects/transition", status_code=303)

    except IntegrityError:
        errors = ["Не удалось удалить связь, поскольку на неё ссылаются другие данные."]
        status_code = 409
    except SQLAlchemyError:
        logging.exception("Ошибка удаления связи преподавателя и предмета")
        errors = ["Не удалось удалить связь. Попробуйте позже."]
        status_code = 500

    try:
        with session() as db_session:
            teacher_subjects = get_teacher_subjects(db_session, user_id)
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": teacher_subjects, "errors": errors}, status_code=status_code)
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки списка связей")
        return templates.TemplateResponse(request=request, name="teacher_subjects/teacher_subjects.html", 
            context={"request": request, "teacher_subjects": [], "errors": ["Не удалось загрузить список предметов преподавателей."]}, status_code=500)

