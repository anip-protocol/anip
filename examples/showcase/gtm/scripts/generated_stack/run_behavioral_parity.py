"""Run deterministic GTM generated-service behavioral parity probes.

This is intentionally not the 490-question LLM bank. It verifies that generated
services in each target language expose the same ANIP service-boundary behavior
for representative success, clarification, approval, denial, and actor-aware
paths.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[5]
DEFAULT_OUTPUT_DIR = REPO_ROOT / "output" / "gtm-parity-conformance"

SERVICE_ORDER = ("pipeline", "enrichment", "prioritization", "outreach")


@dataclasses.dataclass(frozen=True)
class LanguageStack:
    name: str
    start_script: str
    base_port: int
    startup_seconds: float


LANGUAGE_STACKS: dict[str, LanguageStack] = {
    "python": LanguageStack("python", "start_python_generated_stack.py", 4300, 3),
    "typescript": LanguageStack("typescript", "start_typescript_native_stack.py", 4200, 3),
    "go": LanguageStack("go", "start_go_native_stack.py", 4400, 5),
    "java": LanguageStack("java", "start_java_native_stack.py", 4600, 12),
    "csharp": LanguageStack("csharp", "start_csharp_native_stack.py", 4700, 8),
}


BEHAVIOR_CASES: list[dict[str, Any]] = [
    {
        "id": "pipeline-risk-summary-success",
        "service": "pipeline",
        "capability": "gtm.account_risk_summary",
        "actor": "sales_leader",
        "parameters": {"quarter": "2017-Q2", "ranking_basis": "risk_score", "limit": 3},
        "expected_outcome": "success",
    },
    {
        "id": "pipeline-summary-missing-quarter-clarifies",
        "service": "pipeline",
        "capability": "gtm.pipeline_summary",
        "actor": "sales_leader",
        "parameters": {"detail_level": "summary"},
        "expected_outcome": "clarification_required",
    },
    {
        "id": "followup-preparation-approval",
        "service": "pipeline",
        "capability": "gtm.at_risk_followup_preparation",
        "actor": "sales_leader",
        "parameters": {"quarter": "2017-Q2", "ranking_basis": "risk_score"},
        "expected_outcome": "approval_required",
    },
    {
        "id": "followup-preparation-denied",
        "service": "pipeline",
        "capability": "gtm.at_risk_followup_preparation",
        "actor": "sales_analyst",
        "parameters": {"quarter": "2017-Q2", "ranking_basis": "risk_score"},
        "expected_outcome": "denied",
    },
    {
        "id": "reassignment-preparation-approval",
        "service": "pipeline",
        "capability": "gtm.at_risk_reassignment_preparation",
        "actor": "rev_ops_manager",
        "parameters": {"quarter": "2017-Q2", "ranking_basis": "risk_score"},
        "expected_outcome": "approval_required",
    },
    {
        "id": "reassignment-preparation-denied",
        "service": "pipeline",
        "capability": "gtm.at_risk_reassignment_preparation",
        "actor": "sales_analyst",
        "parameters": {"quarter": "2017-Q2", "ranking_basis": "risk_score"},
        "expected_outcome": "denied",
    },
    {
        "id": "enrichment-named-accounts-success",
        "service": "enrichment",
        "capability": "gtm.account_enrichment_summary",
        "actor": "sales_leader",
        "parameters": {"account_names": "Acme Corporation and Codehow"},
        "expected_outcome": "success",
    },
    {
        "id": "lookalike-reference-success",
        "service": "enrichment",
        "capability": "gtm.lookalike_accounts",
        "actor": "sales_leader",
        "parameters": {"reference_account": "Condax", "limit": 3},
        "expected_outcome": "success",
    },
    {
        "id": "route-leads-approval",
        "service": "prioritization",
        "capability": "gtm.route_leads",
        "actor": "sales_leader",
        "parameters": {"cohort_ref": "inbound_last_week", "target_queue": "sales"},
        "expected_outcome": "approval_required",
    },
    {
        "id": "route-leads-denied",
        "service": "prioritization",
        "capability": "gtm.route_leads",
        "actor": "sales_analyst",
        "parameters": {"cohort_ref": "inbound_last_week", "target_queue": "sales"},
        "expected_outcome": "denied",
    },
    {
        "id": "bottleneck-outreach-approval",
        "service": "outreach",
        "capability": "gtm.bottleneck_account_outreach_draft",
        "actor": "sales_leader",
        "parameters": {"quarter": "2017-Q2", "owner_scope": "East", "objective": "first_touch", "channel": "email"},
        "expected_outcome": "approval_required",
    },
]


def _actor_api_keys() -> dict[str, str]:
    sys.path.insert(0, str(REPO_ROOT))
    from examples.showcase.gtm.shared.actor_identity import actor_profiles

    return {actor_id: profile.api_key for actor_id, profile in actor_profiles().items()}


def _service_urls(base_port: int) -> dict[str, str]:
    return {name: f"http://127.0.0.1:{base_port + index}" for index, name in enumerate(SERVICE_ORDER)}


def _http_json(method: str, url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None, timeout: float = 20) -> tuple[int, dict[str, Any]]:
    body = None if payload is None else json.dumps(payload).encode()
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)
    request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason)}


def _wait_for_services(service_urls: dict[str, str], timeout_seconds: float, process: subprocess.Popen[bytes] | None = None) -> None:
    deadline = time.time() + timeout_seconds
    pending = set(service_urls)
    while pending and time.time() < deadline:
        if process is not None and process.poll() is not None:
            raise RuntimeError(f"language stack exited during startup with code {process.returncode}; pending services: {', '.join(sorted(pending))}")
        for service in list(pending):
            status, _payload = _http_json("GET", f"{service_urls[service]}/.well-known/anip", timeout=3)
            if status == 200:
                pending.remove(service)
        if pending:
            time.sleep(0.5)
    if pending:
        raise RuntimeError(f"Timed out waiting for services: {', '.join(sorted(pending))}")


def _start_language(stack: LanguageStack) -> subprocess.Popen[bytes]:
    command = [
        sys.executable,
        str(Path(__file__).with_name(stack.start_script)),
        "--base-port",
        str(stack.base_port),
        "--no-runtime",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([str(REPO_ROOT), env.get("PYTHONPATH", "")])
    return subprocess.Popen(command, cwd=REPO_ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def _discovery(service_url: str) -> dict[str, Any]:
    status, payload = _http_json("GET", f"{service_url}/.well-known/anip")
    if status != 200:
        raise RuntimeError(f"Discovery failed for {service_url}: {status} {payload}")
    return payload["anip_discovery"]


def _minimum_scope(discovery: dict[str, Any], capability: str) -> list[str]:
    metadata = discovery.get("capabilities", {}).get(capability)
    if not isinstance(metadata, dict):
        raise RuntimeError(f"Capability {capability} not found in discovery")
    scope = metadata.get("minimum_scope", [])
    return scope if isinstance(scope, list) else []


def _issue_token(service_url: str, api_key: str, capability: str, scope: list[str], case_id: str) -> str:
    status, payload = _http_json(
        "POST",
        f"{service_url}/anip/tokens",
        payload={
            "scope": scope,
            "capability": capability,
            "purpose_parameters": {"task_id": f"gtm-behavioral-parity:{case_id}"},
        },
        headers={"Authorization": f"Bearer {api_key}"},
    )
    if status != 200 or payload.get("issued") is not True:
        raise RuntimeError(f"Token issuance failed for {capability}: {status} {payload}")
    token = payload.get("token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"Token issuance response did not include token for {capability}: {payload}")
    return token


def _outcome(payload: dict[str, Any]) -> str:
    if payload.get("success") is True:
        return "success"
    failure = payload.get("failure")
    if isinstance(failure, dict):
        return str(failure.get("type") or "unknown")
    return "unknown"


def _invoke_case(service_url: str, api_key: str, case: dict[str, Any]) -> dict[str, Any]:
    discovery = _discovery(service_url)
    scope = _minimum_scope(discovery, str(case["capability"]))
    token = _issue_token(service_url, api_key, str(case["capability"]), scope, str(case["id"]))
    status, payload = _http_json(
        "POST",
        f"{service_url}/anip/invoke/{case['capability']}",
        payload={"parameters": case["parameters"], "client_reference_id": f"parity-{case['id']}"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    outcome = _outcome(payload)
    return {
        "case_id": case["id"],
        "service": case["service"],
        "capability": case["capability"],
        "actor": case["actor"],
        "expected_outcome": case["expected_outcome"],
        "actual_outcome": outcome,
        "passed": outcome == case["expected_outcome"],
        "http_status": status,
        "minimum_scope": scope,
        "failure": payload.get("failure"),
        "result_keys": sorted(payload.get("result", {}).keys()) if isinstance(payload.get("result"), dict) else [],
    }


def _run_language(stack: LanguageStack, *, start_stack: bool, startup_timeout: float) -> dict[str, Any]:
    service_urls = _service_urls(stack.base_port)
    process: subprocess.Popen[bytes] | None = None
    if start_stack:
        process = _start_language(stack)
    try:
        try:
            _wait_for_services(service_urls, timeout_seconds=startup_timeout, process=process)
        except Exception as exc:  # noqa: BLE001 - report startup failures as language failures.
            return {
                "language": stack.name,
                "summary": {"passed": 0, "total": len(BEHAVIOR_CASES)},
                "startup_error": str(exc),
                "cases": [
                    {
                        "case_id": case["id"],
                        "service": case["service"],
                        "capability": case["capability"],
                        "actor": case["actor"],
                        "expected_outcome": case["expected_outcome"],
                        "actual_outcome": "startup_error",
                        "passed": False,
                        "error": str(exc),
                    }
                    for case in BEHAVIOR_CASES
                ],
            }
        api_keys = _actor_api_keys()
        results = []
        for case in BEHAVIOR_CASES:
            service_url = service_urls[str(case["service"])]
            api_key = api_keys[str(case["actor"])]
            try:
                result = _invoke_case(service_url, api_key, case)
            except Exception as exc:  # noqa: BLE001 - report harness failures as case failures.
                result = {
                    "case_id": case["id"],
                    "service": case["service"],
                    "capability": case["capability"],
                    "actor": case["actor"],
                    "expected_outcome": case["expected_outcome"],
                    "actual_outcome": "harness_error",
                    "passed": False,
                    "error": str(exc),
                }
            results.append(result)
        return {
            "language": stack.name,
            "summary": {
                "passed": sum(1 for result in results if result["passed"]),
                "total": len(results),
            },
            "cases": results,
        }
    finally:
        if process is not None:
            _stop_process(process)


def _write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# GTM Generated-Service Behavioral Parity",
        "",
        f"- Generated at: `{report['generated_at']}`",
        f"- Passed: `{report['summary']['passed']}/{report['summary']['total']}`",
        "",
        "| Language | Passed | Total |",
        "| --- | ---: | ---: |",
    ]
    for language in report["languages"]:
        lines.append(f"| {language['language']} | {language['summary']['passed']} | {language['summary']['total']} |")
    lines.extend(["", "## Failures", ""])
    failures = [
        (language["language"], case)
        for language in report["languages"]
        for case in language["cases"]
        if not case["passed"]
    ]
    if not failures:
        lines.append("No failures.")
    else:
        lines.extend(["| Language | Case | Expected | Actual | Detail |", "| --- | --- | --- | --- | --- |"])
        for language, case in failures:
            detail = case.get("error") or case.get("failure") or ""
            detail_text = json.dumps(detail, sort_keys=True) if isinstance(detail, (dict, list)) else str(detail)
            lines.append(
                f"| {language} | `{case['case_id']}` | `{case['expected_outcome']}` | `{case['actual_outcome']}` | {detail_text[:240]} |"
            )
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", action="append", choices=sorted(LANGUAGE_STACKS), dest="languages")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--no-start", action="store_true", help="Use already-running services at each language's default base port.")
    parser.add_argument("--startup-timeout", type=float, default=90)
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args()

    selected = list(LANGUAGE_STACKS) if args.all or not args.languages else args.languages
    started_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    languages = [
        _run_language(LANGUAGE_STACKS[name], start_stack=not args.no_start, startup_timeout=max(args.startup_timeout, LANGUAGE_STACKS[name].startup_seconds))
        for name in selected
    ]
    total = sum(language["summary"]["total"] for language in languages)
    passed = sum(language["summary"]["passed"] for language in languages)
    report = {
        "schema": "anip-gtm-generated-service-behavioral-parity/v0",
        "generated_at": started_at,
        "summary": {"passed": passed, "total": total},
        "languages": languages,
    }

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = started_at.replace(":", "-")
    json_path = output_dir / f"gtm-generated-service-behavioral-parity-{stamp}.json"
    md_path = output_dir / f"gtm-generated-service-behavioral-parity-{stamp}.md"
    latest_json = output_dir / "gtm-generated-service-behavioral-parity-latest.json"
    latest_md = output_dir / "gtm-generated-service-behavioral-parity-latest.md"
    json_payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    json_path.write_text(json_payload)
    latest_json.write_text(json_payload)
    _write_markdown(report, md_path)
    _write_markdown(report, latest_md)
    print(json.dumps({"json": str(json_path), "markdown": str(md_path), "passed": passed, "total": total}, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    raise SystemExit(main())
