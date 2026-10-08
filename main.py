from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from app.database import create_tables
from app.routes.auth import router
from app.templates_config import templates
from dotenv import load_dotenv
import os


app = FastAPI()

create_tables()

app.include_router(router)

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

@app.get("/", tags=["index"])
async def root(request: Request):
    if request.session.get("user_id"):
        return templates.TemplateResponse(request, "index.html")
    return RedirectResponse(url="/auth/login", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)