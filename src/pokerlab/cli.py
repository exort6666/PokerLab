from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from pokerlab.config import LOG_LEVEL
from pokerlab.db.connection import init_db


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


# ============================================================
# init-db
# ============================================================

def cmd_init_db(args: argparse.Namespace) -> int:
    try:
        init_db()
    except Exception as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    print("БД инициализирована")
    return 0


# ============================================================
# import (hand history)
# ============================================================

def cmd_import(args: argparse.Namespace) -> int:
    from pokerlab.db.repo import insert_many
    from pokerlab.hh.pokerok import parse_file

    path = Path(args.path)
    if not path.exists():
        print(f"Путь не найден: {path}", file=sys.stderr)
        return 1

    if path.is_file():
        files = [path]
    else:
        files = sorted(path.glob("*.txt"))

    if not files:
        print(f"Не найдено .txt файлов в {path}", file=sys.stderr)
        return 1

    total_hands = 0
    total_files = 0
    for f in files:
        try:
            hands = parse_file(f)
        except Exception as e:
            print(f"Ошибка парсинга {f.name}: {e}", file=sys.stderr)
            continue
        inserted = insert_many(hands)
        total_hands += inserted
        total_files += 1
        print(f"  {f.name}: {inserted} раздач")

    print(f"\nИтого: {total_hands} раздач из {total_files} файлов")
    return 0


# ============================================================
# import-summaries (tournament results)
# ============================================================

def cmd_import_summaries(args: argparse.Namespace) -> int:
    from pokerlab.db.repo import insert_results_bulk
    from pokerlab.hh.summary import parse_summary_file

    path = Path(args.path)
    if not path.exists():
        print(f"Путь не найден: {path}", file=sys.stderr)
        return 1

    if path.is_file():
        files = [path]
    else:
        files = sorted(path.glob("*.txt"))

    if not files:
        print(f"Не найдено .txt файлов в {path}", file=sys.stderr)
        return 1

    results = []
    skipped_not_summary = 0
    for f in files:
        try:
            r = parse_summary_file(f)
        except Exception as e:
            print(f"Ошибка парсинга {f.name}: {e}", file=sys.stderr)
            continue
        if r is not None:
            results.append(r)
        else:
            skipped_not_summary += 1

    print(f"Распарсено: {len(results)} файлов")
    if skipped_not_summary:
        print(f"Пропущено (не summary): {skipped_not_summary}")

    inserted, skipped = insert_results_bulk(results)
    print(f"Вставлено: {inserted}")
    print(f"Пропущено: {skipped} (уже есть)")
    return 0


# ============================================================
# stats
# ============================================================

def cmd_stats(args: argparse.Namespace) -> int:
    from pokerlab.db.repo import count_hands, count_tournaments, count_results

    tournaments = count_tournaments()
    hands = count_hands()
    results = count_results()
    print(f"Турниров:    {tournaments}")
    print(f"Раздач:      {hands}")
    print(f"Результатов: {results}")
    return 0


# ============================================================
# report
# ============================================================

def cmd_report(args: argparse.Namespace) -> int:
    if args.by == "position":
        from pokerlab.analysis.stats import stats_by_position
        rows = stats_by_position()
        if not rows:
            print("Нет данных")
            return 0
        print(f"{'Pos':>5} {'Рук':>6} {'Net':>10} {'Net/руку':>10} "
              f"{'bb/100':>8} {'VPIP':>6} {'PFR':>6} {'3bet':>6}")
        print("-" * 70)
        total_hands = 0
        total_net = 0
        for r in rows:
            print(f"{r.position:>5} {r.hands:>6d} {r.net:>10d} "
                  f"{r.net_per_hand:>10.2f} {r.bb_per_100:>8.2f} "
                  f"{r.vpip:>6.1f} {r.pfr:>6.1f} {r.three_bet:>6.1f}")
            total_hands += r.hands
            total_net += r.net
        print("-" * 70)
        print(f"{'Всего':>5} {total_hands:>6d} {total_net:>10d}")
        return 0

    if args.by == "stack":
        from pokerlab.analysis.stats import stats_by_stack
        rows = stats_by_stack()
        print(f"{'Стек (BB)':>10} {'Рук':>6} {'Net':>12} "
              f"{'Net/руку':>10} {'bb/100':>8}")
        print("-" * 55)
        total_hands = 0
        total_net = 0
        for r in rows:
            print(f"{r.bucket:>10} {r.hands:>6d} {r.net:>12d} "
                  f"{r.net_per_hand:>10.2f} {r.bb_per_100:>8.2f}")
            total_hands += r.hands
            total_net += r.net
        print("-" * 55)
        print(f"{'Всего':>10} {total_hands:>6d} {total_net:>12d}")
        return 0

    print(f"Неизвестный разрез: {args.by}", file=sys.stderr)
    return 1


# ============================================================
# Parser
# ============================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pokerlab", description="PokerLab CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db", help="Создать БД и схему")
    p_init.set_defaults(func=cmd_init_db)

    p_import = sub.add_parser("import", help="Импортировать hand history")
    p_import.add_argument("path", help="Путь к файлу или папке с .txt")
    p_import.set_defaults(func=cmd_import)

    p_sum = sub.add_parser("import-summaries",
                           help="Импортировать Tournament Summary")
    p_sum.add_argument("path", help="Путь к файлу или папке с .txt")
    p_sum.set_defaults(func=cmd_import_summaries)

    p_stats = sub.add_parser("stats", help="Показать статистику")
    p_stats.set_defaults(func=cmd_stats)

    p_report = sub.add_parser("report", help="Отчёты по своим рукам")
    p_report.add_argument("--by", default="position",
                          choices=["position", "stack"],
                          help="Разрез отчёта")
    p_report.set_defaults(func=cmd_report)

    return parser


def main() -> int:
    setup_logging()
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())