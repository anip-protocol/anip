"""File-backed approval store for the self-contained GTM Python native bundle."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


_LOCK = Lock()


def _store_path() -> Path:
    path = Path(os.getenv("GTM_APPROVAL_STORE_PATH", "/tmp/gtm-python-native-approvals.json"))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_entries() -> list[dict[str, Any]]:
    path = _store_path()
    if not path.exists():
        return []
    return json.loads(path.read_text())


def _write_entries(entries: list[dict[str, Any]]) -> None:
    _store_path().write_text(json.dumps(entries, indent=2, sort_keys=True))


def create_approval_request(*, capability: str, requester: dict[str, Any], required_role: str, preview: dict[str, Any]) -> dict[str, Any]:
    record = {
        "approval_request_id": f"apr_{uuid4().hex[:12]}",
        "capability": capability,
        "status": "pending",
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "requested_by": {
            "actor_id": requester.get("actor_id"),
            "role": requester.get("role"),
            "email": requester.get("principal"),
        },
        "required_role": required_role,
        "preview": preview,
        "approved_at": None,
        "approved_by": None,
    }
    with _LOCK:
        entries = _read_entries()
        entries.append(record)
        _write_entries(entries)
    return record


def list_approval_requests(*, status: str | None = None) -> list[dict[str, Any]]:
    with _LOCK:
        entries = _read_entries()
    if status:
        entries = [item for item in entries if item.get("status") == status]
    return sorted(entries, key=lambda item: str(item.get("requested_at") or ""), reverse=True)


def approve_request(approval_request_id: str, approver: dict[str, Any]) -> dict[str, Any] | None:
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        entries = _read_entries()
        for item in entries:
            if item.get("approval_request_id") != approval_request_id:
                continue
            item["status"] = "approved"
            item["approved_at"] = now
            item["approved_by"] = {
                "actor_id": approver.get("actor_id"),
                "role": approver.get("role"),
                "email": approver.get("principal"),
            }
            _write_entries(entries)
            return item
    return None
