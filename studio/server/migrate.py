"""Run Studio database migrations and exit."""

from __future__ import annotations

from .db import close_pool, init_db, migration_status
from .observability import configure_json_logging


def main() -> None:
    logger = configure_json_logging()
    init_db()
    status = migration_status()
    logger.info(
        "studio_migrate_only_complete",
        extra={
            "event": "studio_migrate_only_complete",
            "applied": status["applied"],
            "applied_count": status["applied_count"],
            "expected_count": status["expected_count"],
            "pending": status["pending"],
        },
    )
    close_pool()


if __name__ == "__main__":
    main()
