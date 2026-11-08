"""Запуск:  python -m app.services.scheduler.tests.run_checks   (без pytest и без БД)"""
import time

from app.services.scheduler import build_result
from app.services.scheduler.verify import verify_rows
from app.services.scheduler.models import RawData
from .fake_data import make_data


def check(name, raw, **kw):
    t = time.perf_counter()
    res = build_result(raw, user_id=1, seed=kw.pop("seed", 1), **kw)
    wall = time.perf_counter() - t
    errs = verify_rows(raw, res.rows)
    assert not errs, errs[:5]
    print(f"{name:34s} уроков={res.total_lessons:4d} поставлено={res.placed:4d} "
          f"не поставлено={len(res.unplaced):3d} качество={res.soft_cost:9.1f} время={wall:5.2f}с "
          f"{'OK' if res.success else 'частично'}")
    return res


if __name__ == "__main__":
    check("маленькая школа", make_data(1, 6, 8, 12, 6, 5, 3, 1, teachers_per_subject=2))
    r = check("колледж (типично)", make_data(2))
    check("колледж, seed 3", make_data(3))
    check("большой (40 групп)", make_data(4, 40, 16, 80, 6, 28, 16, 3))
    r = check("перегруз: мало аудиторий", make_data(5, 20, 14, 30, 6, 4, 2, 1))
    print("   причины:", {u["reason"] for u in r.unplaced})
    r = check("перегруз: мало преподавателей", make_data(6, 20, 14, 10, 6, teachers_per_subject=2))
    check("пустые данные", RawData())
