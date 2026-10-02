from fastapi import FastAPI
from urllib import request
import uvicorn
from starlette.templating import Jinja2Templates
from database import create_tables

app = FastAPI()
create_tables()

templates = Jinja2Templates(directory="app/templates")

@app.get("/", tags=["index"])
def root():
    return templates.TemplateResponse({"request": request}, "login.html")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)