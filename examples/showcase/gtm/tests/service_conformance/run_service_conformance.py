#!/usr/bin/env python3
"""Run deterministic GTM service conformance cases against one ANIP service."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ACTOR_BEARERS = {
    "sales_leader": "demo-sales-leader-key",
    "account_manager_east": "demo-account-manager-east-key",
    "sales_analyst": "demo-sales-analyst-key",
    "rev_ops_manager": "demo-rev-ops-manager-key",
}


@dataclass(frozen=True)
class CaseResult:
    case_id: str
    ok: bool
    expected: str
    observed: str
    detail: str


def _post_json(url: str, payload: dict[str, Any], bearer: str) -> tuple[int, dict[str, Any]]:
    data = json.dumps(payload).encode("utf-8")
    request = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {bearer}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=20.0) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            payload = json.loads(body) if body else {}
        except json.JSONDecodeError:
            payload = {"raw_body": body}
        return exc.code, payload
    except URLError as exc:
        raise RuntimeError(f"request failed for {url}: {exc}") from exc


def _issue_token(base_url: str, case: dict[str, Any]) -> str:
    actor = str(case.get("actor") or "sales_leader")
    bearer = str(case.get("bearer") or ACTOR_BEARERS.get(actor) or "").strip()
    if not bearer:
        raise ValueError(f"case {case.get('id')} has unknown actor and no bearer: {actor}")
    capability = str(case["capability"])
    scope = case.get("scope") or [capability]
    status, payload = _post_json(
        f"{base_url.rstrip('/')}/anip/tokens",
        {
            "subject": "agent:gtm-service-conformance",
            "scope": scope,
            "capability": capability,
            "purpose_parameters": {"source": "gtm_service_conformance", "actor_id": actor},
        },
        bearer,
    )
    if status >= 400 or not payload.get("issued"):
        raise RuntimeError(f"token issuance failed for {case.get('id')}: HTTP {status} {payload}")
    return str(payload["token"])


def _observed_status(payload: dict[str, Any]) -> str:
    if payload.get("success") is True:
        status = str(payload.get("status") or payload.get("outcome") or "").strip()
        return status or "completed"
    failure = payload.get("failure")
    if isinstance(failure, dict):
        failure_type = str(failure.get("type") or "").strip()
        if failure_type:
            return failure_type
    return "unknown"


def _run_case(base_url: str, case: dict[str, Any]) -> CaseResult:
    case_id = str(case.get("id") or case.get("capability") or "unnamed")
    expected = str(case["expected_status"])
    token = _issue_token(base_url, case)
    payload: dict[str, Any] = {"parameters": case.get("parameters") or {}}
    requested_effects = case.get("requested_effects")
    if requested_effects is not None:
        payload["requested_effects"] = requested_effects
    status, response = _post_json(
        f"{base_url.rstrip('/')}/anip/invoke/{case['capability']}",
        payload,
        token,
    )
    observed = _observed_status(response)
    ok = observed == expected
    detail = "" if ok else f"HTTP {status} {json.dumps(response, sort_keys=True)}"
    return CaseResult(case_id=case_id, ok=ok, expected=expected, observed=observed, detail=detail)


def _load_cases(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        raise ValueError("cases file must contain a JSON array")
    return [item for item in data if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Base URL for the generated ANIP service")
    parser.add_argument("--cases", required=True, type=Path, help="Path to service conformance cases JSON")
    args = parser.parse_args()

    results = [_run_case(args.base_url, case) for case in _load_cases(args.cases)]
    failures = [result for result in results if not result.ok]
    for result in results:
        status = "PASS" if result.ok else "FAIL"
        print(f"{status} {result.case_id}: expected={result.expected} observed={result.observed}")
        if result.detail:
            print(f"  {result.detail}")
    print(f"\n{len(results) - len(failures)}/{len(results)} service conformance cases passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
