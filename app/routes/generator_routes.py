import logging
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import delete
from sqlalchemy.exc import SQLAlchemyError

from app.database import session, Schedules
from app.templates_config import templates
from app.services.generator import generate_schedule, ScheduleGenerationError

router = APIRouter(prefix="/generator")

logging.basicConfig(filename="app.log", filemode="a", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")


def get_user_id(request: Request): return request.session.get("user_id")


# ============================================================
# READ: страница генератора расписания
# ============================================================

@router.get("/transition", name="transition_to_generator", tags=["generator"])
async def generator_page(request: Request):
    user_id = get_user_id(request)
    if user_id is None: return RedirectResponse(url="/auth/login", status_code=303)

    return templates.TemplateResponse(request=request, name="generator/generator.html", context={"request": request, "errors": []})


# ============================================================
# CREATE: запуск алгоритма генерации расписания
# ============================================================

@router.post("/generate", name="generator.generate", tags=["generator"])
async def run_schedule_generation(request: Request):
    user_id = get_user_id(request)
    if user_id is None: return RedirectResponse(url="/auth/login", status_code=303)

    try:
        result = generate_schedule(user_id)
        if result.total_lessons == 0:
            return templates.TemplateResponse(request=request, name="generator/generator.html", 
                context={"request": request, "errors": ["Нет данных для формирования расписания. Проверьте заполнение учебного плана, групп, дисциплин, преподавателей и слотов."]}, 
                status_code=400)

        request.session["flash_success"] = f"Расписание успешно сформировано! Размещено занятий: {result.placed} из {result.total_lessons}."
        return RedirectResponse(url="/schedules/transition", status_code=303)

    except ScheduleGenerationError as e:
        logging.exception("Ошибка ограничений при генерации расписания")
        errors = ["Ошибка ограничений при генерации расписания"] 
        status_code = 400
    except SQLAlchemyError:
        logging.exception("Ошибка БД при генерации расписания")
        errors = ["Ошибка базы данных при формировании расписания."] 
        status_code = 500
    except Exception as e:
        logging.error(f"{e}, file: generator_routes.py/generate")
        print("Ошибка в generator_routes.py:", e)
        errors = ["Не удалось сформировать расписание. Проверьте корректность введённых данных."]
        status_code = 500

    return templates.TemplateResponse(request=request, name="generator/generator.html", 
        context={"request": request, "errors": errors}, status_code=status_code)



# ============================================================
# DELETE: полная очистка текущего расписания
# ============================================================

@router.post("/clear", name="generator.clear", tags=["generator"])
async def clear_schedule(request: Request):
    user_id = get_user_id(request)
    if user_id is None: return RedirectResponse(url="/auth/login", status_code=303)

    try:
        with session() as db_session:
            db_session.execute(delete(Schedules).where(Schedules.user_id == user_id))
            db_session.commit()

        request.session["flash_success"] = "Расписание успешно очищено."
        return RedirectResponse(url="/generator/transition", status_code=303)

    except SQLAlchemyError:
        logging.exception("Ошибка очистки расписания через генератор")
        return templates.TemplateResponse(request=request, name="generator/generator.html", 
            context={"request": request, "errors": ["Не удалось очистить расписание. Попробуйте позже."]}, status_code=500)
