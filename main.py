# import uvicorn
# from fastapi import FastAPI, Response
# from starlette.templating import Jinja2Templates
# from fastapi.staticfiles import StaticFiles
# from Moduls.Database import Database
#
# app = FastAPI()
# DB = Database()
# app.mount("/static", StaticFiles(directory="static"), name="static")
#
# templates = Jinja2Templates(directory="templates")
#
#
# @app.get("/")
# def index(response: Response):
#     data = {"title": "TECHSTORE"}
#
#     return templates.TemplateResponse( {"request": response},"main.html", context=data)
#
# @app.get("/catalog")
# def catalog(response: Response):
#     data = {"catalog": DB.query(query='SELECT name FROM catalog;')}
#     DB.commit()
#     return data
#
# if __name__ == "__main__":
#     uvicorn.run(app, host="127.0.0.1", port=8000)
#
from urllib import request
import psycopg2
from fastapi import FastAPI, Request
import uvicorn
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from Moduls.Database import Database
# templates = Jinja2Templates(directory="templates")
#
# app = FastAPI()
# DB = Database()
#
# app.mount("/static", StaticFiles(directory="static"), name="static")
#
# @app.get("/", tags=["items"])
# def read_root():
#     query = DB.query('SELECT * FROM qwerty;')[0][0]
#
#     return templates.TemplateResponse({"request": request}, "main.html", {"query": query, "title": query})
#
# if __name__ == '__main__':
#     uvicorn.run(app, host="127.0.0.1", port=8000)



templates = Jinja2Templates(directory="templates")

app = FastAPI()

DB = Database()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def glavnaya():
    data = DB.query("SELECT * FROM qwerty;")
    return templates.TemplateResponse({"request": request}, "main.html", {"qwerqwer": data, "qweshka": '12345678'})

@app.get("/W")
def W():
    return templates.TemplateResponse({"request": request}, "contact.html")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)