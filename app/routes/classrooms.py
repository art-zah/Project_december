import logging
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.database import session, Classrooms, Schedules
from app.templates_config import templates
from app.pedant import Classroom


router = APIRouter(prefix="/classrooms")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s",)


def validate_classroom(room_number: str, capacity: str, room_type: str):
    """Проверяет данные формы, пробелы по краям строк удаляются до проверки"""
    return Classroom(room_number=room_number.strip(), capacity=capacity, room_type=room_type.strip())


def get_user_id(request: Request):
    """Возвращает ID авторизованного пользователя или None"""
    return request.session.get("user_id")


def get_classroom(db_session, classroom_id: int, user_id: int):
    """Возвращает аудиторию только текущего пользователя"""
    return db_session.execute(select(Classrooms).where(Classrooms.id == classroom_id, 
        Classrooms.user_id == user_id,)).scalars().first()


def classroom_form_response(request: Request, template_name: str, errors: list, room_number: str = "",
    capacity: str = "", room_type: str = "", status_code: int = 400, classroom=None):
    """Повторно отображает форму с введёнными данными и ошибками."""

    context = {"request": request,"errors": errors, "room_number": room_number, "capacity": capacity, "room_type": room_type}

    if classroom is not None:
        context["classroom"] = classroom

    return templates.TemplateResponse(request=request, name=template_name, context=context, status_code=status_code)

# ============================================================
# READ: список преподавателей
# ============================================================

@router.get("/transition", tags=["classrooms"])
async def transition_to_classrooms(request: Request):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            classrooms = db_session.execute(select(Classrooms).where(Classrooms.user_id == user_id).order_by(Classrooms.id)).scalars().all()

        return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
            context={"request": request, "classrooms": classrooms})

    except SQLAlchemyError:
        logging.exception("Ошибка получения списка аудиторий")
        return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
            context={"request": request, "classrooms": [], "errors": ["Не удалось загрузить список аудиторий."]}, status_code=500)


# ============================================================
# CREATE: форма добавления аудитории
# ============================================================

@router.get("/create", tags=["classrooms"])
async def create_classroom_page(request: Request):
    if get_user_id(request) is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(request=request, name="classrooms/create_classroom.html", context={"request": request, "errors": []})


# ============================================================
# CREATE: сохранение аудитории
# ============================================================

@router.post("/create", tags=["classrooms"])
async def create_classroom(request: Request, room_number: str = Form(""), capacity: str = Form(""), room_type: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    errors = []

    try:
        int(capacity)
        data = validate_classroom(room_number, capacity, room_type)

        with session() as db_session:
            classroom = Classrooms(user_id=user_id, room_number=data.room_number, capacity=data.capacity, room_type=data.room_type)
            db_session.add(classroom)
            db_session.commit()

        request.session["flash_success"] = "Аудитория успешно добавлена."

        return RedirectResponse(url="/classrooms/create", status_code=303)

    except ValidationError as e:
        for error in e.errors():
            field = error["loc"][0]

            if field == "room_number":
                errors.append("Номер аудитории обязателен и должен содержать не более 20 символов.")
            elif field == "capacity":
                errors.append("Вместимость должна быть положительным целым числом.")
            elif field == "room_type":
                errors.append("Тип аудитории обязателен и должен содержать не более 50 символов.")
        status_code = 400

    except IntegrityError:
        errors.append("Аудитория с таким номером уже существует или нарушены ограничения")
        status_code = 400

    except Exception as e:
        logging.error(f"{e}, file: classrooms.py/create")
        print("Ошибка в classrooms.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")
        status_code = 500

    return classroom_form_response(request=request, template_name="classrooms/create_classroom.html", errors=errors,
        room_number=room_number, capacity=capacity, room_type=room_type, status_code=status_code)

# ============================================================
# UPDATE: форма редактирования
# ============================================================

@router.get("/update/{id}", tags=["classrooms"])
async def edit_classroom_page(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            classroom = get_classroom(db_session, id, user_id)

            if classroom is None:
                return templates.TemplateResponse(request=request, name="classrooms/classrooms.html", 
                    context={"request": request, "errors": ["Аудитория не найдена"]}, status_code=404)

            # Сохраняем значения для отображения формы.
            classroom_data = {"id": classroom.id, "room_number": classroom.room_number, "capacity": classroom.capacity, "room_type": classroom.room_type}

        return templates.TemplateResponse(request=request, name="classrooms/edit_classroom.html",
            context={"request": request, "classroom": classroom_data, "errors": []})

    except Exception as e:
        logging.error(f"{e}, file: classrooms.py/update")
        print("Ошибка в classrooms.py:", e)
        return templates.TemplateResponse(request=request, name="classrooms/update/{id}.html",
            context={"request": request, "errors": ["Неизвестная ошибка, попробуйте повторить действия позже"]}, status_code=500)


# ============================================================
# UPDATE: сохранение изменений
# ============================================================

@router.post("/update/{id}", tags=["classrooms"])
async def edit_classroom(request: Request, id: int, room_number: str = Form(""), capacity: str = Form(""), room_type: str = Form("")):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    errors = []

    try:
        int(capacity)
        data = validate_classroom(room_number, capacity, room_type)

        with session() as db_session:
            classroom = get_classroom(db_session, id, user_id)

            if classroom is None:
                return templates.TemplateResponse(request=request, name="classrooms/classrooms.html", 
                    context={"request": request, "errors": ["Аудитория не найдена"]}, status_code=404)
                
            classroom.room_number = data.room_number
            classroom.capacity = data.capacity
            classroom.room_type = data.room_type

            db_session.commit()

        request.session["flash_success"] = "Данные аудитории обновлены."

        return RedirectResponse(url="/classrooms/transition", status_code=303)

    except ValidationError as e:
        for error in e.errors():
            field = error["loc"][0]

            if field == "room_number":
                errors.append("Номер аудитории обязателен и должен содержать не более 20 символов.")
            elif field == "capacity":
                errors.append("Вместимость должна быть положительным целым числом.")
            elif field == "room_type":
                errors.append("Тип аудитории обязателен и должен содержать не более 50 символов.")
            status_code = 400

    except IntegrityError:
        errors.append("Аудитория с таким номером уже существует или нарушены ограничения")
        status_code = 400

    except Exception as e:
        logging.error(f"{e}, file: classrooms.py/update/edit")
        print("Ошибка в classrooms.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")
        status_code = 500

    # Повторно проверяем владельца и получаем данные записи.
    try:
        with session() as db_session:
            classroom = get_classroom(db_session, id, user_id)

            if classroom is None:
                try:
                    with session() as db_session:
                        classrooms = db_session.execute(select(Classrooms).where(Classrooms.user_id == user_id).order_by(Classrooms.id)).scalars().all()
            
                    return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
                        context={"request": request, "classrooms": classrooms, "errors": ["Аудитория не найдена"]}, status_code=404)
            
                except SQLAlchemyError:
                    logging.exception("Ошибка получения списка аудиторий")
                    return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
                        context={"request": request, "classrooms": [], "errors": ["Не удалось загрузить список аудиторий."]}, status_code=500)

            classroom_data = {"id": classroom.id, "room_number": room_number, "capacity": capacity, "room_type": room_type}

    except Exception as e:
        logging.error(f"{e}, file: classrooms.py/update/edit")
        print("Ошибка в classrooms.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")
        status_code = 500

    return classroom_form_response(request=request, template_name="classrooms/edit_classroom.html", errors=errors,
        room_number=room_number, capacity=capacity, room_type=room_type, classroom=classroom_data, status_code=status_code)

# ============================================================
# DELETE: удаление аудитории
# ============================================================

@router.post("/delete/{id}", tags=["classrooms"])
async def delete_classroom(request: Request, id: int):
    user_id = get_user_id(request)

    if user_id is None:
        return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            classroom = get_classroom(db_session, id, user_id)

            if classroom is None:
                try:
                    with session() as db_session:
                        classrooms = db_session.execute(select(Classrooms).where(Classrooms.user_id == user_id).order_by(Classrooms.id)).scalars().all()
            
                    return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
                        context={"request": request, "classrooms": classrooms, "errors": ["Аудитория не найдена"]}, status_code=404)
            
                except SQLAlchemyError:
                    logging.exception("Ошибка получения списка аудиторий")
                    return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
                        context={"request": request, "classrooms": [], "errors": ["Не удалось загрузить список аудиторий."]}, status_code=500)

            # Не удаляем аудиторию, если она уже используется в существующем расписании.
            schedule_exists = db_session.execute(select(Schedules.id).where(Schedules.classroom_id == id, Schedules.user_id == user_id).limit(1)).first()

            if schedule_exists:
                return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
                    context={"request": request, 
                        "errors": ["Нельзя удалить аудиторию: она используется в расписании. Сначала измените или удалите соответствующие записи расписания."]},
                    status_code=409)
            db_session.delete(classroom)
            db_session.commit()

        request.session["flash_success"] = "Аудитория успешно удалена."

        return RedirectResponse(url="/classrooms/transition", status_code=303)

    except IntegrityError:
        return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
            context={"request": request, "errors": ["Аудиторию нельзя удалить, поскольку на неё ссылаются другие записи."]}, status_code=409)

    except Exception as e:
        logging.error(f"{e}, file: classrooms.py/delete")
        print("Ошибка в classrooms.py:", e)
        return templates.TemplateResponse(request=request, name="classrooms/classrooms.html",
            context={"request": request, "errors": ["Неизвестная ошибка, попробуйте повторить действия позже"]}, status_code=500)