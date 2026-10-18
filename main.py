from fastapi import FastAPI, Request, status
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import uvicorn
from starlette.middleware.sessions import SessionMiddleware
from app.database import create_tables
from app.routes.auth import router as auth_router 
from app.templates_config import templates
from app.routes.index import router as index_router
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

app.include_router(auth_router)
app.include_router(index_router)


@app.get("/", tags=["root"])
async def root(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/index", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse(url="/auth/login", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)