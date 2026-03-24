"""Storage probe — snapshots SQLite state and detects unexpected mutations."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field

# Tables whose row-count changes are expected (lease churn, etc.)
_ALLOWLISTED_TABLES: frozenset[str] = frozenset(
    {"exclusive_leases", "leader_leases"}
)


@dataclass(frozen=True)
class TableSnapshot:
    """Immutable snapshot of a single table's row count."""

    table_name: str
    row_count: int


@dataclass(frozen=True)
class Finding:
    """A single finding from a storage comparison."""

    table: str
    change_type: str  # e.g. "row_count_increased", "row_count_decreased"
    detail: str
    severity: str  # "violation" or "warning"


class StorageProbe:
    """Takes before/after snapshots of a SQLite database."""

    def __init__(self, storage_dsn: str) -> None:
        # Accept ``sqlite:///path`` or a raw file path.
        if storage_dsn.startswith("sqlite:///"):
            self.db_path = storage_dsn[len("sqlite:///"):]
        elif storage_dsn.startswith("sqlite://"):
            self.db_path = storage_dsn[len("sqlite://"):]
        else:
            self.db_path = storage_dsn

    def snapshot(self) -> dict[str, TableSnapshot]:
        """Return a mapping of table name -> :class:`TableSnapshot`."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            result: dict[str, TableSnapshot] = {}
            for table in tables:
                count = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()[0]  # noqa: S608
                result[table] = TableSnapshot(table_name=table, row_count=count)
            return result
        finally:
            conn.close()

    @staticmethod
    def compare(
        before: dict[str, TableSnapshot],
        after: dict[str, TableSnapshot],
        expected_audit_delta: int = 1,
    ) -> list[Finding]:
        """Compare two snapshots and return findings for unexpected changes."""
        findings: list[Finding] = []

        all_tables = set(before) | set(after)
        for table in sorted(all_tables):
            before_count = before[table].row_count if table in before else 0
            after_count = after[table].row_count if table in after else 0
            delta = after_count - before_count

            if delta == 0:
                continue

            # Allowlisted lease tables — report as informational only.
            if table in _ALLOWLISTED_TABLES:
                continue

            # Audit table — allow expected delta.
            if table in ("audit_log", "audit_entries", "audit"):
                if delta == expected_audit_delta:
                    continue
                findings.append(
                    Finding(
                        table=table,
                        change_type="unexpected_audit_delta",
                        detail=(
                            f"Expected audit delta {expected_audit_delta}, "
                            f"got {delta} (before={before_count}, after={after_count})"
                        ),
                        severity="warning",
                    )
                )
                continue

            # New table appeared.
            if table not in before:
                findings.append(
                    Finding(
                        table=table,
                        change_type="table_created",
                        detail=f"New table '{table}' with {after_count} rows",
                        severity="violation",
                    )
                )
                continue

            # Unexpected row-count change.
            change_type = "row_count_increased" if delta > 0 else "row_count_decreased"
            findings.append(
                Finding(
                    table=table,
                    change_type=change_type,
                    detail=(
                        f"Table '{table}' changed by {delta} rows "
                        f"(before={before_count}, after={after_count})"
                    ),
                    severity="violation",
                )
            )

        return findings
