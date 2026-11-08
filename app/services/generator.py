"""Фасад для остального проекта: `from app.services.generator import generate_schedule`."""
from app.services.scheduler import generate_schedule, GenerationResult, ScheduleGenerationError

__all__ = ["generate_schedule", "GenerationResult", "ScheduleGenerationError"]