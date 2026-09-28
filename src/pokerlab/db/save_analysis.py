"""Сохранение классификации спотов в БД."""

from __future__ import annotations

import logging

from pokerlab.analysis.spot_classifier import SpotInfo, classify_all
from pokerlab.db.connection import transaction

log = logging.getLogger(__name__)


def save_spots(spots: list[SpotInfo]) -> int:
    """Сохранить споты в hand_analysis. Возвращает число вставленных."""
    count = 0
    with transaction() as conn:
        for spot in spots:
            try:
                conn.execute("""
                    INSERT INTO hand_analysis (
                        hand_id, spot_type, street, solver_name, solver_version,
                        hero_action, optimal_action, ev_optimal, ev_actual,
                        ev_loss, is_correct, is_critical, details
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, 0, NULL)
                    ON CONFLICT(hand_id) DO UPDATE SET
                        spot_type = excluded.spot_type,
                        street = excluded.street,
                        hero_action = excluded.hero_action,
                        solver_name = excluded.solver_name
                """, (
                    spot.hand_id,
                    spot.spot_type.value,
                    spot.street,
                    "spot_classifier",
                    "v1.0",
                    spot.hero_action.action if spot.hero_action else None,
                ))
                count += 1
            except Exception as e:
                log.error("Ошибка для %s: %s", spot.hand_id, e)

    return count


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    print("Классифицирую раздачи...")
    spots = classify_all()
    print(f"Классифицировано: {len(spots)}")

    print("Сохраняю в БД...")
    n = save_spots(spots)
    print(f"Сохранено: {n}")


if __name__ == "__main__":
    main()