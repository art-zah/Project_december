from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.templates_config import templates
from sqlalchemy import select, func

from app.database import session, Teachers, Groups, Subjects, Classrooms, Schedules, TeacherConstraints

router = APIRouter()


@router.get("/index", tags=["index"])
async def transition_to_index(request: Request):
    user_id = request.session.get("user_id")

    if not user_id:
        return RedirectResponse(url="/auth/login", status_code=303)

    with session() as db:
        statistics = {"teachers_count": db.scalar(select(func.count())
            .select_from(Teachers).where(Teachers.user_id == user_id)) or 0,
            
            "groups_count": db.scalar(select(func.count()).select_from(Groups)
                .where(Groups.user_id == user_id)) or 0,
                
            "subjects_count": db.scalar(select(func.count()).select_from(Subjects)
                .where(Subjects.user_id == user_id)) or 0,
                
            "classrooms_count": db.scalar(select(func.count()).select_from(Classrooms)
                .where(Classrooms.user_id == user_id)) or 0,
            
            "schedule_count": db.scalar(select(func.count()).select_from(Schedules)
                .where(Schedules.user_id == user_id)) or 0,
            
            "teacher_constraint_count": db.scalar(select(func.count()).select_from(TeacherConstraints)
                .where(TeacherConstraints.user_id == user_id)) or 0,}

        return templates.TemplateResponse(request=request, name="index.html", context={"statistics": statistics, "request": request})