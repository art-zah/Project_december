import os
from sqlalchemy import create_engine, Integer, String, Time, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Mapped, mapped_column
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL is None:
    raise RuntimeError("DATABASE_URL не найден в .env")

engine = create_engine(DATABASE_URL)

session = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

class Users(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(225), nullable=False)

class Classroom(Base):
    __tablename__ = "classrooms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_class"),
        UniqueConstraint("user_id", "room_number", name="user_id_room_number_class"),
        
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_class"))

class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    room_type: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_sub"),
        UniqueConstraint("user_id", "name", name="user_id_name_sub"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_sub"))

class Timeslot(Base):
    __tablename__ = "timeslots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    day_of_week: Mapped[str] = mapped_column(String(20), nullable=False)
    lesson_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[object] = mapped_column(Time, nullable=False)
    end_time: Mapped[object] = mapped_column(Time, nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_time"),
                      
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_time"))

class Teacher(Base):
    __tablename__ = "teachers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    max_lessons_per_day: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_t"),
                      
        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_t"))

class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    course: Mapped[int] = mapped_column(Integer, nullable=False)
    speciality: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_g"),
        UniqueConstraint("user_id", "name", "course", name="user_id_name_course_g"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_g"))

class TeacherConstraint(Base):
    __tablename__ = "teacher_constraints"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timeslot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, nullable=False)
    constraint_type: Mapped[str] = mapped_column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_t_c"),
        UniqueConstraint("user_id", "timeslot_id", "teacher_id", name="user_id_timeslot_id_teacher_id_t_c"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_t_c"),
        ForeignKeyConstraint(["timeslot_id", "user_id"], ["timeslots.id", "timeslots.user_id"], name="fk_timeslot_t_c"),
        ForeignKeyConstraint(["teacher_id", "user_id"], ["teachers.id", "teachers.user_id"], name="fk_teacher_t_c"))

class TeacherSubject(Base):
    __tablename__ = "teacher_subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (UniqueConstraint("id", "user_id", name="id_user_id_t_s"),
        UniqueConstraint("user_id", "teacher_id", "subject_id", name="user_id_teacher_id_subject_id_t_s"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_t_s"),
        ForeignKeyConstraint(["teacher_id", "user_id"], ["teachers.id", "teachers.user_id"], name="fk_teacher_t_s"),
        ForeignKeyConstraint(["subject_id", "user_id"], ["subjects.id", "subjects.user_id"], name="fk_subject_t_s"))

class GroupSubjectLimit(Base):
    __tablename__ = "group_subject_limits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    max_lessons_per_week: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "user_id", name="id_user_id_g_s"),
        UniqueConstraint("user_id", "group_id", "subject_id", name="user_id_group_id_subject_id_g_s"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_g_s"),
        ForeignKeyConstraint(["group_id", "user_id"], ["groups.id", "groups.user_id"], name="fk_group_g_s"),
        ForeignKeyConstraint(["subject_id", "user_id"], ["subjects.id", "subjects.user_id"], name="fk_subject_g_s"))

class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    group_id: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, nullable=False)
    teacher_id: Mapped[int] = mapped_column(Integer, nullable=False)
    classroom_id: Mapped[int] = mapped_column(Integer, nullable=False)
    timeslot_id: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        UniqueConstraint("id", "user_id", name="id_user_id_s"),
        UniqueConstraint("group_id", "timeslot_id", name="no_groups"),
        UniqueConstraint("teacher_id", "timeslot_id", name="no_teacher"),
        UniqueConstraint("classroom_id", "timeslot_id", name="no_classroom"),

        ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_user_s"),
        ForeignKeyConstraint(["group_id", "user_id"], ["groups.id", "groups.user_id"],name="fk_group_s"),
        ForeignKeyConstraint(["subject_id", "user_id"], ["subjects.id", "subjects.user_id"], name="fk_subject_s"),
        ForeignKeyConstraint(["teacher_id", "user_id"], ["teachers.id", "teachers.user_id"], name="fk_teacher_s"),
        ForeignKeyConstraint(["classroom_id", "user_id"], ["classrooms.id", "classrooms.user_id"], name="fk_classroom_s"),
        ForeignKeyConstraint(["timeslot_id", "user_id"], ["timeslots.id", "timeslots.user_id"], name="fk_timeslot_s"))


def create_tables():
    Base.metadata.create_all(engine)

def add_data(data):
    session.add(data)
    session.commit()