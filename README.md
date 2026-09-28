# PokerLab

Инструмент для анализа и тренировки в MTT NLHE.

## Цель

Разбор своих турниров PokerOK/GG после игры:
- импорт hand history;
- фильтры по позициям, стекам, стадиям;
- equity-калькулятор;
- ICM и push/fold;
- заметки и теги к рукам;
- тренажёр префлопа.

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows
pip install -r requirements.txt
pip install -e .