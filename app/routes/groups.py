import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Groups, Schedules, GroupSubjectLimits
from app.templates_config import templates
from app.pedant import Group


router = APIRouter(prefix="/groups")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None."""
    return request.session.get("user_id")


def validate_group(name: str, course: str, speciality: str):
    """Проверяет данные учебной группы."""
    return Group(name=name.strip(), course=course, speciality=speciality.strip())


def get_group(db_session, group_id: int, user_id: int):
    """Возвращает группу только текущего пользователя."""
    return db_session.execute(select(Groups).where(Groups.id == group_id, Groups.user_id == user_id)).scalars().first()


def get_groups(db_session, user_id: int):
    """Возвращает список групп текущего пользователя."""
    return db_session.execute(select(Groups).where(Groups.user_id == user_id).order_by(Groups.id)).scalars().all()


def group_to_dict(group):
    """Преобразует группу в словарь для шаблона."""
    return {"id": group.id, "name": group.name, "course": group.course, "speciality": group.speciality}


def group_form_response(request: Request, template_name: str, errors: list, name: str = "",
    course: str = "", speciality: str = "", group=None, status_code: int = 400):
    """Повторно отображает форму с введёнными данными и ошибками."""

    context = {"request": request, "errors": errors, "name": name, "course": course, "speciality": speciality}

    if group is not None:
        context["group"] = group

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)


def group_validation_errors(e: ValidationError):
    """Преобразует ошибки Pydantic в понятные сообщения."""
    errors = []

    for error in e.errors():
        field = error["loc"][0]

        if field == "name":
            errors.append("Название группы обязательно и должно содержать не более 100 символов.")
        elif field == "course":
            errors.append("Курс должен быть положительным целым числом больше 1.")
        elif field == "speciality":
            errors.append("Специальность обязательна и должна содержать не более 100 символов.")
            
    return errors


# ============================================================
# READ: список групп
# ============================================================

@router.get("/transition", name="transition_to_groups", tags=["groups"])
async def transition_to_groups(request: Request):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            groups = get_groups(db_session, user_id)
            groups_data = [group_to_dict(group) for group in groups]
        return templates.TemplateResponse(request=request, name="groups/groups.html", 
            context={"request": request, "groups": groups_data, "errors": []})
    except SQLAlchemyError:
        logging.exception("Ошибка получения списка учебных групп")
        return templates.TemplateResponse(request=request, name="groups/groups.html", 
            context={"request": request, "groups": [], "errors": ["Не удалось загрузить список учебных групп."]}, status_code=500)


# ============================================================
# CREATE: форма добавления группы
# ============================================================

@router.get("/create", name="groups.create", tags=["groups"])
async def create_group_page(request: Request):
    if get_user_id(request) is None:
        return RedirectResponse(url="/auth/login", status_code=303)
    return templates.TemplateResponse(request=request, name="groups/create_group.html", 
        context={"request": request, "errors": [], "name": "", "course": "", "speciality": ""})


# ============================================================
# CREATE: сохранение группы
# ============================================================

@router.post("/create", name="groups.create_submit", tags=["groups"])
async def create_group(request: Request, name: str = Form(""), course: str = Form(""), speciality: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_group(name, course, speciality)
        with session() as db_session:
            group = Groups(user_id=user_id, name=data.name, course=data.course, speciality=data.speciality)
            db_session.add(group)
            db_session.commit()
        request.session["flash_success"] = "Учебная группа успешно добавлена."
        return RedirectResponse(url="/groups/create", status_code=303)

    except ValidationError as e:
        errors = group_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Группа с таким названием и курсом уже существует или нарушены ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка создания учебной группы")
        errors = ["Не удалось сохранить группу. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: groups.py/create")
        print("Ошибка в groups.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    return group_form_response(request, "groups/create_group.html", errors, name, course, speciality, status_code=status_code)


# ============================================================
# UPDATE: форма редактирования группы
# ============================================================

@router.get("/update/{id}", name="groups.edit", tags=["groups"])
async def edit_group_page(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            group = get_group(db_session, id, user_id)
            if group is None:
                return RedirectResponse(url="/groups/transition", status_code=303)
            group_data = group_to_dict(group)

        return templates.TemplateResponse(request=request, name="groups/edit_group.html", 
            context={"request": request, "group": group_data, "errors": []})

    except SQLAlchemyError:
        logging.exception("Ошибка открытия формы редактирования учебной группы")
        return templates.TemplateResponse(request=request, name="groups/groups.html", 
            context={"request": request, "groups": [], "errors": ["Не удалось загрузить данные учебной группы."]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений группы
# ============================================================

@router.post("/update/{id}", name="groups.edit_submit", tags=["groups"])
async def edit_group(request: Request, id: int, name: str = Form(""), course: str = Form(""), speciality: str = Form("")):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        data = validate_group(name, course, speciality)

        with session() as db_session:
            group = get_group(db_session, id, user_id)

            if group is None:
                return RedirectResponse(url="/groups/transition", status_code=303)

            group.name = data.name
            group.course = data.course
            group.speciality = data.speciality
            db_session.commit()

        request.session["flash_success"] = "Данные учебной группы обновлены."
        return RedirectResponse(url="/groups/transition", status_code=303)

    except ValidationError as e:
        errors = group_validation_errors(e)
        status_code = 400
    except IntegrityError:
        errors = ["Группа с таким названием и курсом уже существует или нарушены ограничения базы данных."]
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка обновления учебной группы")
        errors = ["Не удалось обновить группу. Попробуйте позже."]
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: groups.py/edit")
        print("Ошибка в groups.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
        status_code = 500

    try:
        with session() as db_session:
            group = get_group(db_session, id, user_id)
            if group is None:
                return RedirectResponse(url="/groups/transition", status_code=303)
            group_data = group_to_dict(group)
            group_data.update({"name": name, "course": course, "speciality": speciality})

        return group_form_response(request, "groups/edit_group.html", errors, name, course, speciality, group_data, status_code=status_code)

    except SQLAlchemyError:
        logging.exception("Ошибка повторной загрузки формы учебной группы")
        return templates.TemplateResponse(request=request, name="groups/groups.html", 
            context={"request": request, "groups": [], "errors": ["Не удалось загрузить данные учебной группы."]}, status_code=500)


# ============================================================
# DELETE: удаление группы
# ============================================================

@router.post("/delete/{id}", name="groups.delete", tags=["groups"])
async def delete_group(request: Request, id: int):
    user_id = get_user_id(request)
    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            group = get_group(db_session, id, user_id)

            if group is None:
                return RedirectResponse(url="/groups/transition", status_code=303)
            groups = get_groups(db_session, user_id)
            groups_data = [group_to_dict(group) for group in groups]
            has_schedules = db_session.execute(select(Schedules.id).where(Schedules.group_id == id, Schedules.user_id == user_id).limit(1)).first()
            has_limits = db_session.execute(select(GroupSubjectLimits.id).where(GroupSubjectLimits.group_id == id, GroupSubjectLimits.user_id == user_id).limit(1)).first()

            if has_schedules or has_limits:
                return templates.TemplateResponse(request=request, name="groups/groups.html",
                    context={"request": request, "groups": groups_data, "errors": ["Нельзя удалить группу: она используется в расписании или учебном плане. Сначала удалите или измените связанные записи."]},
                    status_code=409)

            db_session.delete(group)
            db_session.commit()

        request.session["flash_success"] = "Учебная группа успешно удалена."
        return RedirectResponse(url="/groups/transition", status_code=303)

    except IntegrityError:
        return templates.TemplateResponse(request=request, name="groups/groups.html",
            context={"request": request, "groups": groups_data, "errors": ["Группу нельзя удалить, поскольку на неё ссылаются другие записи."]},
            status_code=409)
    except SQLAlchemyError:
        logging.exception("Ошибка удаления учебной группы")
        errors = ["Не удалось удалить группу. Попробуйте позже."]  
    except Exception as e:
        logging.error(f"{e}, file: groups.py/delete")
        print("Ошибка в groups.py:", e)
        errors = ["Неизвестная ошибка, попробуйте повторить действия позже."]
    
    return templates.TemplateResponse(request=request, name="groups/groups.html",
        context={"request": request, "groups": groups_data, "errors": errors},
        status_code=500)
