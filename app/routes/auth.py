from fastapi import APIRouter, status, Request, Form, HTTPException
from fastapi.responses import RedirectResponse
from app.database import session, Users
from app.pedant import User
from app.templates_config import templates
from pydantic import ValidationError
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
import logging

router = APIRouter(prefix="/auth") # подключаем роутер

password_hash = PasswordHash.recommended() # на будущее, для удобного использования хеширования
logging.basicConfig(filename='app.log', filemode='a', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s') # тоже на будущее, для удобной записи в app.log


@router.get("/register", tags=["register"])
async def transition_to_register(request: Request):
    return templates.TemplateResponse(request=request, name="auth/register.html", context={"request": request})

@router.post("/register", tags=["register"], status_code=status.HTTP_201_CREATED)
async def user_register(request: Request, username: str = Form(...), password: str = Form(...)):
    errors = []
    try:
        User(username=username, password=password)
        heshed_password = password_hash.hash(password)
        userORM = Users(username=username, password_hash=heshed_password)
        with session() as db_sesion:
            db_sesion.add(userORM)
            db_sesion.commit()
            user_id = userORM.id
        request.session["flash_success"] = "Регистрация прошла успешно!"
        request.session["user_id"] = user_id
        return RedirectResponse(url="/index", status_code=303)

    except ValidationError:
        if not username or not password:
            errors.append('Поля "Логин" и "Пароль" обязательны и не могут быть пустыми')

        if len(username) > 50 or len(username) < 1:
            errors.append('Поле "Логин" не должно быть меньше 1 символа и не должно превышать 50 символов')

        if len(password) < 7:
            errors.append('Поле "Пароль" не должно быть меньше 7 символов')

    except IntegrityError:
        errors.append("Пользователь уже существует")

    except Exception as e:
        logging.error(f"{e}, file: auth.py/register")
        print("Ошибка в auth.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")

    return templates.TemplateResponse(request=request, name="auth/register.html",
        context={"errors": errors, "username": username}, status_code=400)


@router.get("/login", tags=["auth"])
async def transition_to_login(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/index", status_code=303)
    return templates.TemplateResponse(request=request, name="auth/login.html", context={"request": request})

@router.post("/login", tags=["auth"])
async def user_login(request: Request, username: str = Form(...), password: str = Form(...)):
    errors = []
    try:
        User(username=username, password=password)
        with session() as db_session:
            user = db_session.execute(
                select(Users).where(Users.username == username)
            ).scalars().first()

            if not user or not password_hash.verify(password, user.password_hash):
                raise HTTPException(status_code=404, detail="Неверный логин или пароль")

            request.session.clear()
            request.session["flash_success"] = "Вы успешно вошли!"
            request.session["username"] = username
            request.session["user_id"] = user.id
            return RedirectResponse(url="/index", status_code=303)
        
    except ValidationError:
        errors.append("Некорректные данные")
        return templates.TemplateResponse(request=request, name="auth/login.html", 
            context={"errors": errors, "username": username}, status_code=422)

    except HTTPException:
        errors.append("Неверный логин или пароль")
        return templates.TemplateResponse(request=request, name="auth/login.html", 
            context={"errors": errors, "username": username}, status_code=401)
        
    except Exception as e:
        logging.error(f"{e}, file: auth.py/login")
        print("Ошибка в auth.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")

    return templates.TemplateResponse(request=request, name="auth/login.html",
            context={"errors": errors, "username": username}, status_code=400)


@router.get("/logout", tags=["logout"])
async def logout(request: Request):

    request.session.clear()

    return RedirectResponse(url="/auth/login", status_code=303)