from fastapi import APIRouter, status, Request, Form
from fastapi.responses import RedirectResponse
from app.database import session, Users
from app.pedant import User
from app.templates_config import templates
from pydantic import ValidationError
from pwdlib import PasswordHash
from sqlalchemy.exc import IntegrityError
import logging

router = APIRouter(prefix="/auth")

password_hash = PasswordHash.recommended()
logging.basicConfig(filename='app.log', filemode='a', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')

@router.get("/register", tags=["register"])
async def transition_to_register(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/register", tags=["register"], status_code=status.HTTP_201_CREATED)
async def user_register(request: Request, username: str = Form(...), password: str = Form(...)):
    errors = []
    try:
        
        User(username=username, password=password)
        heshed_password = password_hash.hash(password)
        userORM = Users(username=username, password_hash=heshed_password)
        with session() as sesion:
            sesion.add(userORM)
            sesion.commit()
            user_id = userORM.id
        request.session["flash_success"] = "Регистрация прошла успешно!"
        request.session["user_id"] = user_id
        return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)

    except ValidationError:
        if not username or not password:
            errors.append("Поля Логин и Пароль обязательны и не могут быть пустыми")

        if len(username) > 50 or len(username) < 1:
            errors.append("Поле Логин не должно быть меньше 1 символа и не должно превышать 50 символов")

        if len(password) < 7:
            errors.append("Поле Пароль не должно быть меньше 7 символов")

    except IntegrityError:
        errors.append("Пользователь уже существует")

    except Exception as e:
        logging.error(f"{e}, file: auth.py")
        print("Ошибка в auth.py:", e)
        errors.append("Неизвестная ошибка, попробуйте повторить действия позже")

    return templates.TemplateResponse(request=request, name="auth/register.html",
        context={"errors": errors, "username": username}, status_code=400)

@router.get("/login", tags=["auth"])
async def transition_to_login(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.get("/logout")
async def logout(request: Request):

    request.session.clear()

    return RedirectResponse(url="/auth/login", status_code=303)