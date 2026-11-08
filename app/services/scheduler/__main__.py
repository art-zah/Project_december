"""Запуск из консоли:  python -m app.services.scheduler --user-id 1 [--dry-run] [--time-limit 8] [--seed 1]"""
import argparse
import json

from . import generate_schedule


def main():
    ap = argparse.ArgumentParser(description="Генерация расписания для пользователя")
    ap.add_argument("--user-id", type=int, required=True)
    ap.add_argument("--time-limit", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true", help="не записывать результат в БД")
    a = ap.parse_args()
    res = generate_schedule(a.user_id, time_limit=a.time_limit, seed=a.seed, save=not a.dry_run)
    print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
