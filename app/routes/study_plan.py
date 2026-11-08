import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, GroupSubjectLimits, Groups, Subjects
from app.templates_config import templates
from app.pedant import StudyPlan


router = APIRouter(prefix="/study_plan")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_study_plan(group_id: str, subject_id: str, lessons_per_week: str):
    """Проверяет данные учебного плана."""
    return StudyPlan(group_id=group_id, subject_id=subject_id, lessons_per_week=lessons_per_week)


def get_study_plan(db_session, study_plan_id: int, user_id: int):
    """Возвращает запись учебного плана только текущего пользователя."""
    return db_session.execute(select(GroupSubjectLimits)
        .where(GroupSubjectLimits.id == study_plan_id, GroupSubjectLimits.user_id == user_id)).scalars().first()


def get_study_plans(db_session, user_id: int):
    """Возвращает список учебных планов текущего пользователя с группами и предметами."""
    result = db_session.execute(select(GroupSubjectLimits, Groups, Subjects)
        .join(Groups, (Groups.id == GroupSubjectLimits.group_id) & (Groups.user_id == GroupSubjectLimits.user_id))
        .join(Subjects, (Subjects.id == GroupSubjectLimits.subject_id) & (Subjects.user_id == GroupSubjectLimits.user_id))
        .where(GroupSubjectLimits.user_id == user_id).order_by(GroupSubjectLimits.id)).all()
    return [{"id": sp.id, "group_id": sp.group_id, "subject_id": sp.subject_id, "lessons_per_week": sp.lessons_per_week, 
        "group": {"name": group.name}, "subject": {"name": subject.name}} for sp, group, subject in result]


def get_groups(db_session, user_id: int):
    """Возвращает список учебных групп текущего пользователя."""
    groups = db_session.execute(select(Groups).where(Groups.user_id == user_id).order_by(Groups.name)).scalars().all()
    return [{"id": group.id, "name": group.name} for group in groups]


def get_subjects(db_session, user_id: int):
    """Возвращает список дисциплин текущего пользователя."""
    subjects = db_session.execute(select(Subjects).where(Subjects.user_id == user_id).order_by(Subjects.name)).scalars().all()
    return [{"id": subject.id, "name": subject.name} for subject in subjects]


def study_plan_form_response(request: Request, template_name: str, errors: list, groups: list, subjects: list, group_id: str = "", 
        subject_id: str = "", lessons_per_week: str = "", plan=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""

    context = {"request": request, "errors": errors, "groups": groups, "subjects": subjects, "group_id": group_id, "subject_id": subject_id, 
        "lessons_per_week": lessons_per_week}
    
    if plan is not None:
        context["plan"] = plan

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def study_plan_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []
    for error in e.errors():
        field = error["loc"][0]
        if field == "group_id":
            errors.append("Необходимо выбрать учебную группу.")
        elif field == "subject_id":
            errors.append("Необходимо выбрать предмет.")
        elif field == "lessons_per_week":
            errors.append("Количество пар в неделю должно быть положительным целым числом.")
    return errors


def check_study_plan_relations(db_session, group_id: int, subject_id: int, user_id: int):
    """Проверяет, что группа и предмет принадлежат текущему пользователю."""
    group = db_session.execute(select(Groups.id).where(Groups.id == group_id, Groups.user_id == user_id)).first()
    subject = db_session.execute(select(Subjects.id).where(Subjects.id == subject_id, Subjects.user_id == user_id)).first()
    return group is not None and subject is not None


# ============================================================
# READ: список учебных планов
# ============================================================

@router.get("/transition", name="transition_to_study_plan", tags=["study_plan"])
async def transition_to_study_plan(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            plans = get_study_plans(db_session, user_id)
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": plans, "errors": []})
    except SQLAlchemyError:
        logging.exception("Ошибка получения списка учебных планов")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось загрузить учебный план."]}, status_code=500)


# ============================================================
# CREATE: форма добавления учебного плана
# ============================================================

@router.get("/create", name="study_plan.create", tags=["study_plan"])
async def create_study_plan_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            groups = get_groups(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
        return study_plan_form_response(request, "study_plan/create_study_plan.html", errors=[], groups=groups, subjects=subjects)
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы создания учебного плана")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось загрузить данные для формы."]}, status_code=500)


# ============================================================
# CREATE: сохранение учебного плана
# ============================================================

@router.post("/create", name="study_plan.create_submit", tags=["study_plan"])
async def create_study_plan(request: Request, group_id: str = Form(""), subject_id: str = Form(""), lessons_per_week: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_study_plan(group_id, subject_id, lessons_per_week)
        with session() as db_session:
            if not check_study_plan_relations(db_session, data.group_id, data.subject_id, user_id):
                groups = get_groups(db_session, user_id)
                subjects = get_subjects(db_session, user_id)
                return study_plan_form_response(request, "study_plan/create_study_plan.html", 
                    errors=["Выбранная группа или предмет не найдены."], groups=groups, subjects=subjects, group_id=group_id, 
                    subject_id=subject_id, lessons_per_week=lessons_per_week, status_code=400)

            study_plan = GroupSubjectLimits(user_id=user_id, group_id=data.group_id, subject_id=data.subject_id, 
                lessons_per_week=data.lessons_per_week)
            db_session.add(study_plan)
            db_session.commit()

        request.session["flash_success"] = "Запись учебного плана успешно добавлена."
        return RedirectResponse(url="/study_plan/create", status_code=303)

    except ValidationError as e:
        errors = study_plan_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Для данной группы этот предмет уже добавлен в учебный план."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания учебного плана")
        errors = ["Не удалось сохранить учебный план. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: study_plan.py/create")
        print("Ошибка в study_plan.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            groups = get_groups(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
        return study_plan_form_response(request, "study_plan/create_study_plan.html", errors=errors, groups=groups, subjects=subjects, 
            group_id=group_id, subject_id=subject_id, lessons_per_week=lessons_per_week, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы создания учебного плана")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось загрузить данные формы."]}, status_code=500)


# ============================================================
# UPDATE: форма редактирования учебного плана
# ============================================================

@router.get("/update/{id}", name="study_plan.edit", tags=["study_plan"])
async def edit_study_plan_page(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            study_plan = get_study_plan(db_session, id, user_id)
            if study_plan is None:
                return RedirectResponse(url="/study_plan/transition", status_code=303)

            groups = get_groups(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
            study_plan_data = {"id": study_plan.id, "group_id": study_plan.group_id, "subject_id": study_plan.subject_id, 
                "lessons_per_week": study_plan.lessons_per_week}

        return study_plan_form_response(request, "study_plan/edit_study_plan.html", errors=[], groups=groups, subjects=subjects, 
            group_id=str(study_plan_data["group_id"]), subject_id=str(study_plan_data["subject_id"]), 
            lessons_per_week=str(study_plan_data["lessons_per_week"]), plan=study_plan_data)
    
    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования учебного плана")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось открыть форму редактирования учебного плана."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений учебного плана
# ============================================================

@router.post("/update/{id}", name="study_plan.edit_submit", tags=["study_plan"])
async def edit_study_plan(request: Request, id: int, group_id: str = Form(""), subject_id: str = Form(""), lessons_per_week: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_study_plan(group_id, subject_id, lessons_per_week)
        with session() as db_session:
            study_plan = get_study_plan(db_session, id, user_id)
            if study_plan is None:
                return RedirectResponse(url="/study_plan/transition", status_code=303)

            if not check_study_plan_relations(db_session, data.group_id, data.subject_id, user_id):
                groups = get_groups(db_session, user_id)
                subjects = get_subjects(db_session, user_id)
                study_plan_data = {"id": study_plan.id, "group_id": study_plan.group_id, "subject_id": study_plan.subject_id, 
                    "lessons_per_week": study_plan.lessons_per_week}
                
                return study_plan_form_response(request, "study_plan/edit_study_plan.html", errors=["Выбранная группа или предмет не найдены."], 
                    groups=groups, subjects=subjects, group_id=group_id, subject_id=subject_id, lessons_per_week=lessons_per_week, 
                    plan=study_plan_data, status_code=400)

            study_plan.group_id = data.group_id
            study_plan.subject_id = data.subject_id
            study_plan.lessons_per_week = data.lessons_per_week
            db_session.commit()

        request.session["flash_success"] = "Запись учебного плана успешно обновлена."
        return RedirectResponse(url="/study_plan/transition", status_code=303)

    except ValidationError as e:
        errors = study_plan_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Для данной группы этот предмет уже добавлен в учебный план."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка редактирования учебного плана")
        errors = ["Не удалось обновить учебный план. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: study_plan.py/edit")
        print("Ошибка в study_plan.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            study_plan = get_study_plan(db_session, id, user_id)
            if study_plan is None:
                return RedirectResponse(url="/study_plan/transition", status_code=303)
            groups = get_groups(db_session, user_id)
            subjects = get_subjects(db_session, user_id)
            study_plan_data = {"id": study_plan.id, "group_id": study_plan.group_id, "subject_id": study_plan.subject_id, 
                "lessons_per_week": lessons_per_week}
            
        return study_plan_form_response(request, "study_plan/edit_study_plan.html", errors=errors, groups=groups, subjects=subjects, 
            group_id=group_id, subject_id=subject_id, lessons_per_week=lessons_per_week, plan=study_plan_data, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы редактирования учебного плана")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось обновить учебный план. Попробуйте позже."]}, status_code=500)


# ============================================================
# DELETE: удаление записи учебного плана
# ============================================================

@router.post("/delete/{id}", name="study_plan.delete", tags=["study_plan"])
async def delete_study_plan(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            study_plan = get_study_plan(db_session, id, user_id)
            if study_plan is None:
                return RedirectResponse(url="/study_plan/transition", status_code=303)

            db_session.delete(study_plan)
            db_session.commit()

        request.session["flash_success"] = "Запись учебного плана успешно удалена."
        return RedirectResponse(url="/study_plan/transition", status_code=303)

    except IntegrityError:
        errors = ["Не удалось удалить запись учебного плана из-за связанных данных."]
        status_code = 409
    except SQLAlchemyError:
        logging.exception("Ошибка удаления учебного плана")
        errors = ["Не удалось удалить запись учебного плана. Попробуйте позже."]
        status_code = 500

    try:
        with session() as db_session:
            plans = get_study_plans(db_session, user_id)
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": plans, "errors": errors}, status_code=status_code)
    
    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки списка учебных планов")
        return templates.TemplateResponse(request=request, name="study_plan/study_plan.html", 
            context={"request": request, "plans": [], "errors": ["Не удалось загрузить список учебных планов."]}, status_code=500)
