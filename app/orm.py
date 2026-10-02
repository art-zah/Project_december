from sqlalchemy import create_engine, text, MetaData, Table, Integer, String, Column, ForeignKey
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase, Mapped, mapped_column
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(
    DATABASE_URL
)


session = sessionmaker(bind=engine)


with engine.connect() as connect:
    result = connect.execute(text("select * from qwerty"))
    print(result.fetchall())

class Base(DeclarativeBase):
    pass

class MenORM(Base):
    __tablename__ = "qwerty"

    id: Mapped[int] = mapped_column("id", primary_key=True)
    username: Mapped[str] = mapped_column("username", )



playerMenOrm = MenORM(id=3, name="Nizor")
with session() as sesion:
    sesion.add(playerMenOrm)
    sesion.commit()
