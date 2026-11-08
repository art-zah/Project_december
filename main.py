from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from app.database import create_tables
from app.routes import auth, index, classrooms, teachers, constraints, timeslots, groups, subjects, teacher_subjects, study_plan, schedules, generator_routes
from app.templates_config import templates
from dotenv import load_dotenv
import os

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY не задан, проверьте .env")

app = FastAPI()

create_tables()

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

app.include_router(auth.router)
app.include_router(index.router)
app.include_router(classrooms.router)
app.include_router(teachers.router)
app.include_router(constraints.router)
app.include_router(timeslots.router)
app.include_router(groups.router)
app.include_router(subjects.router)
app.include_router(teacher_subjects.router)
app.include_router(study_plan.router)
app.include_router(schedules.router)
app.include_router(generator_routes.router)

@app.get("/", tags=["root"])
async def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/index", status_code=303)
    return RedirectResponse(url="/auth/login", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)