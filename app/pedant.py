from pydantic import BaseModel, Field
from datetime import time

class User(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=7)

class Classroom(BaseModel):
    room_number: str = Field(min_length=1, max_length=20)
    capacity: int = Field(gt=0)
    room_type: str = Field(min_length=1, max_length=50)

class Teacher(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    max_lessons_per_day: int = Field(gt=0)

class Constraint(BaseModel):
    teacher_id: int = Field(gt=0)
    timeslot_id: int = Field(gt=0)
    constraint_type: str = Field(min_length=1, max_length=50)

class Timeslot(BaseModel):
    day_of_week: str = Field(min_length=1, max_length=20)
    lesson_number: int = Field(gt=0)
    start_time: time
    end_time: time

class Group(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    course: int = Field(ge=1)
    speciality: str = Field(min_length=1, max_length=100)

class Subject(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    room_type: str = Field(min_length=1, max_length=50)

class TeacherSubject(BaseModel):
    teacher_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)

class StudyPlan(BaseModel):
    group_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)
    lessons_per_week: int = Field(gt=0)

class Schedule(BaseModel):
    group_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)
    teacher_id: int = Field(gt=0)
    classroom_id: int = Field(gt=0)
    timeslot_id: int = Field(gt=0)
