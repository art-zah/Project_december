"""Модуль генерации расписания.

    from app.services.scheduler import generate_schedule
    result = generate_schedule(user_id)

Подробности — в api.py; настройки и веса — в config.py.
"""
from .api import generate_schedule, build_result, ScheduleGenerationError
from .models import GenerationResult

__all__ = ["generate_schedule", "build_result", "ScheduleGenerationError", "GenerationResult"]
