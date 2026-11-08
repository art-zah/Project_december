# Модуль генерации расписания

```python
from app.services.scheduler import generate_schedule   # или from app.services.generator import ...
result = generate_schedule(user_id)                     # читает данные user_id, пишет в schedules
result.success, result.placed, result.unplaced, result.warnings
```
Функция синхронная и считает до `time_limit` секунд (по умолчанию 8) — в FastAPI вызывать из обычного `def`-эндпоинта
или через `run_in_threadpool`. `save=False` — пробный прогон без записи; `python -m app.services.scheduler --user-id 1 --dry-run`.

## Правила
Жёсткие (никогда не нарушаются, перед записью проверяются отдельным `verify.py`): группа / преподаватель / аудитория
не в двух местах в один слот; преподаватель ведёт предмет (`teacher_subjects`); тип аудитории = `subjects.room_type`;
преподаватель не в запрещённый слот; `max_lessons_per_day`; число пар предмета у группы не больше `max_lessons_per_week` (генератор старается набрать именно столько; если не помещается — недобор попадёт в `unplaced`, это не ошибка).
Мягкие (оптимизируются, веса в `config.py`): без «окон» у групп и преподавателей, ровная нагрузка по дням, один предмет
у группы не дважды в день, один преподаватель на (группа, предмет), ранние пары, пожелания преподавателей.

## Файлы
config (веса, словари) · models · problem (БД→индексы, отсев невыполнимого) · state (сетка + стоимость) ·
construct (жадно + вытеснение) · optimize (отжиг) · solver · verify · db_io (единственный код с БД, всё по user_id) · api · tests/
