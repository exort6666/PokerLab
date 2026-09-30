"""
Проверка логов ночного расчёта.
Печатает сводку (OK/ERR/skip) + последние 30 строк последнего лога.
"""

from pathlib import Path

log_dir = Path("C:/Dev/PokerLab")
logs = sorted(log_dir.glob("overnight_*.log"))

if not logs:
    print("Нет логов overnight_*.log")
    raise SystemExit

latest = logs[-1]
print(f"Последний лог: {latest.name}")
print()

text = latest.read_text(encoding="utf-8", errors="replace")
lines = text.splitlines()

ok = sum(1 for l in lines if " OK " in l and "[" in l)
err = sum(1 for l in lines if " ERR " in l and "[" in l)
skip = sum(1 for l in lines if "[skip]" in l)
stages = [l for l in lines if "STAGE" in l or "DONE in" in l]

print(f"OK:   {ok}")
print(f"ERR:  {err}")
print(f"Skip: {skip}")
print()
print("Стадии:")
for s in stages:
    print(f"  {s}")
print()
print("=== Последние 30 строк ===")
for l in lines[-30:]:
    print(l)