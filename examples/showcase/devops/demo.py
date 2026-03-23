#!/usr/bin/env python3
"""DevOps Infrastructure Showcase Demo — 8-step scripted ANIP interaction.

A deterministic walkthrough of ANIP governance and infrastructure features
using the DevOps infrastructure showcase app.  Not an autonomous agent
loop — each step is a scripted HTTP call with formatted output.

Start the server first:
    python app.py &

Run the demo:
    python demo.py
    python demo.py --base-url http://some-other-host:9000
    BASE_URL=http://... python demo.py
"""

from __future__ import annotations

import argparse
import os
import sys

import httpx

# ---------------------------------------------------------------------------
# Formatting helpers (matches finance demo style)
# ---------------------------------------------------------------------------

def print_header(step: int, title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"STEP {step}: {title}")
    print(f"{'=' * 60}")


def print_action(method: str, path: str) -> None:
    print(f"\n  -> {method} {path}")


def print_kv(key: str, value: object, indent: int = 6) -> None:
    print(f"{' ' * indent}{key}: {value}")


# ---------------------------------------------------------------------------
# Demo runner
# ---------------------------------------------------------------------------

class DevOpsDemo:
    """Eight-step scripted ANIP interaction against the DevOps showcase."""

    API_KEY_PLATFORM = "platform-key"
    API_KEY_APPTEAM = "appteam-key"
    API_KEY_CI = "ci-key"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10)

        # State accumulated across steps
        self.platform_token_id: str = ""
        self.platform_jwt: str = ""
        self.appteam_token_id: str = ""
        self.appteam_jwt: str = ""
        self.ci_jwt: str = ""
        self.rollback_jwt: str = ""

    # -- helpers --

    def _auth_api_key(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"}

    def _auth_jwt(self, jwt: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {jwt}"}

    def _post(self, path: str, *, json_body: dict | None = None,
              headers: dict[str, str] | None = None,
              params: dict[str, str] | None = None) -> dict:
        resp = self.client.post(path, json=json_body, headers=headers, params=params)
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self.client.get(path)
        resp.raise_for_status()
        return resp.json()

    # -- steps --

    def run(self) -> None:
        print("ANIP DevOps Infrastructure Showcase")
        print(f"Server: {self.base_url}")
        print(f"Platform key: {self.API_KEY_PLATFORM} -> human:platform-engineer@example.com")
        print(f"App-team key: {self.API_KEY_APPTEAM} -> human:app-developer@example.com")
        print(f"CI key:       {self.API_KEY_CI} -> agent:ci-pipeline")

        steps = [
            self.step_1_discovery,
            self.step_2_scoped_delegation,
            self.step_3_infrastructure_overview,
            self.step_4_health_check,
            self.step_5_scale_operation,
            self.step_6_purpose_bound_token,
            self.step_7_scope_enforcement,
            self.step_8_audit_and_health,
        ]
        for step_fn in steps:
            try:
                step_fn()
            except Exception as exc:
                print(f"\n  !! Error: {exc}")
                print("     (continuing to next step)")

        print(f"\n{'=' * 60}")
        print("DEMO COMPLETE")
        print(f"{'=' * 60}")
        print("\nFeatures demonstrated:")
        print("  1. Discovery — capability advertisement with all four side-effect types")
        print("  2. Scoped delegation — platform -> app-team -> CI agent, each narrowing scope")
        print("  3. Infrastructure overview — read-only deployment listing via delegated token")
        print("  4. Health check — service health metrics via delegated token")
        print("  5. Scale operation — write operation (scale replicas) via delegated token")
        print("  6. Scope-bound rollback token — infra.deploy scope for incident response")
        print("  7. Scope enforcement — repeated delete_resource denials with structured failure")
        print("  8. Audit + health — audit log with event_class and /-/health endpoint")

    # ---- Step 1: Discovery ----

    def step_1_discovery(self) -> None:
        print_header(1, "DISCOVERY")
        print_action("GET", "/.well-known/anip")

        disco = self._get("/.well-known/anip")
        anip = disco["anip_discovery"]

        print_kv("protocol", anip["protocol"])
        print_kv("compliance", anip["compliance"])
        print_kv("trust_level", anip["trust_level"])

        # Health endpoint availability
        health_ep = anip.get("health_endpoint")
        print_kv("health_endpoint", health_ep if health_ep else "/-/health (default)")

        # Fetch manifest for side-effect info
        manifest = self._get("/anip/manifest")
        print("\n      Capabilities and side effects (all four types):")
        for cap_name in anip["capabilities"]:
            cap = manifest["capabilities"].get(cap_name, {})
            se = cap.get("side_effect", {})
            se_type = se.get("type", "unknown") if isinstance(se, dict) else se
            scope = cap.get("minimum_scope", [])
            print(f"        - {cap_name:25s}  side_effect={se_type:15s}  scope={scope}")

        # Highlight the four types
        print("\n      Side-effect types present: read, write, transactional, irreversible")

    # ---- Step 2: Scoped Delegation ----

    def step_2_scoped_delegation(self) -> None:
        print_header(2, "SCOPED DELEGATION")

        # Hop 1: Platform engineer issues broad token to app-developer
        print("      Hop 1: Platform engineer -> app-developer (read + write + deploy + admin)")
        print_action("POST", "/anip/tokens (platform: broad)")
        platform_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "human:app-developer@example.com",
                "scope": ["infra.read", "infra.write", "infra.deploy", "infra.admin"],
                "capability": "list_deployments",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not platform_resp.get("issued"):
            print_kv("ERROR", platform_resp)
            return
        self.platform_token_id = platform_resp["token_id"]
        self.platform_jwt = platform_resp["token"]
        print_kv("token_id", self.platform_token_id)
        print_kv("scope", "infra.read, infra.write, infra.deploy, infra.admin")
        print_kv("delegated_to", "human:app-developer@example.com")

        # Hop 2: App-developer narrows and delegates to CI agent (read + write only)
        print("\n      Hop 2: App-developer -> CI agent (narrows to read + write)")
        print_action("POST", "/anip/tokens (appteam: narrowed delegation via parent)")
        appteam_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.read", "infra.write"],
                "capability": "list_deployments",
                "parent_token": self.platform_token_id,
            },
            headers=self._auth_api_key(self.API_KEY_APPTEAM),
        )
        if not appteam_resp.get("issued"):
            print_kv("ERROR", appteam_resp)
            return
        self.appteam_token_id = appteam_resp["token_id"]
        self.appteam_jwt = appteam_resp["token"]
        self.ci_jwt = appteam_resp["token"]
        print_kv("token_id", self.appteam_token_id)
        print_kv("scope", "infra.read, infra.write")
        print_kv("delegated_to", "agent:ci-pipeline")

        print("\n      Hierarchy: platform-engineer (read+write+deploy+admin)")
        print("                   -> app-developer -> ci-pipeline (read+write)")

    # ---- Step 3: Infrastructure Overview ----

    def step_3_infrastructure_overview(self) -> None:
        print_header(3, "INFRASTRUCTURE OVERVIEW")

        # Issue a read-only token for listing deployments
        print_action("POST", "/anip/tokens (read-only for list_deployments)")
        read_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.read"],
                "capability": "list_deployments",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not read_resp.get("issued"):
            print_kv("ERROR", read_resp)
            return
        read_jwt = read_resp["token"]

        print_action("POST", "/anip/invoke/list_deployments")
        result = self._post(
            "/anip/invoke/list_deployments",
            json_body={"parameters": {}},
            headers=self._auth_jwt(read_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        deployments = result["result"]["deployments"]
        print_kv("count", result["result"]["count"])
        print(f"\n      {'Service':<25} {'Version':<12} {'Replicas':>8} {'Status':<10} {'Env'}")
        print(f"      {'-'*25} {'-'*12} {'-'*8} {'-'*10} {'-'*12}")
        for d in deployments:
            print(f"      {d['name']:<25} {d['version']:<12} {d['replicas']:>8} {d['status']:<10} {d['environment']}")

    # ---- Step 4: Health Check ----

    def step_4_health_check(self) -> None:
        print_header(4, "HEALTH CHECK")

        # Issue a read-only token for health check
        print_action("POST", "/anip/tokens (read-only for get_service_health)")
        health_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.read"],
                "capability": "get_service_health",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not health_resp.get("issued"):
            print_kv("ERROR", health_resp)
            return
        health_jwt = health_resp["token"]

        print_action("POST", "/anip/invoke/get_service_health (api-gateway)")
        result = self._post(
            "/anip/invoke/get_service_health",
            json_body={"parameters": {"service_name": "api-gateway"}},
            headers=self._auth_jwt(health_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        health = result["result"]
        print_kv("service", health["name"])
        print_kv("status", health["status"])
        print_kv("uptime_seconds", f"{health['uptime_seconds']:,}")
        print_kv("error_rate", f"{health['error_rate']:.3%}")
        print_kv("latency_p50_ms", f"{health['latency_p50_ms']}ms")
        print_kv("latency_p99_ms", f"{health['latency_p99_ms']}ms")

    # ---- Step 5: Scale Operation ----

    def step_5_scale_operation(self) -> None:
        print_header(5, "SCALE OPERATION")

        # Issue a write token for scaling
        print_action("POST", "/anip/tokens (write scope for scale_replicas)")
        scale_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.write"],
                "capability": "scale_replicas",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not scale_resp.get("issued"):
            print_kv("ERROR", scale_resp)
            return
        scale_jwt = scale_resp["token"]

        print(f"\n      Scaling api-gateway from 3 to 5 replicas (write operation)")
        print_action("POST", "/anip/invoke/scale_replicas (api-gateway, 5)")
        result = self._post(
            "/anip/invoke/scale_replicas",
            json_body={"parameters": {"service_name": "api-gateway", "replicas": 5}},
            headers=self._auth_jwt(scale_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        scale = result["result"]
        print_kv("event_id", scale["event_id"])
        print_kv("service_name", scale["service_name"])
        print_kv("previous_replicas", scale["previous_replicas"])
        print_kv("new_replicas", scale["new_replicas"])
        print_kv("status", scale["status"])

    # ---- Step 6: Scope-Bound Rollback Token ----

    def step_6_purpose_bound_token(self) -> None:
        print_header(6, "SCOPE-BOUND ROLLBACK TOKEN (centerpiece)")
        print("      Platform engineer issues a rollback-only token via infra.deploy scope.")
        print("      Purpose parameters (incident-response, target api-gateway) are metadata,")
        print("      not enforced by the handler — scope is what restricts the token.\n")

        # Issue a scope-bound token for rollback only
        print_action("POST", "/anip/tokens (scope: infra.deploy, rollback only)")
        rollback_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.deploy"],
                "capability": "rollback_deployment",
                "purpose_parameters": {
                    "reason": "incident-response",
                    "target_service": "api-gateway",
                },
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not rollback_resp.get("issued"):
            print_kv("ERROR", rollback_resp)
            return
        self.rollback_jwt = rollback_resp["token"]
        print_kv("token_id", rollback_resp["token_id"])
        print_kv("scope", "infra.deploy")
        print_kv("capability", "rollback_deployment")
        print_kv("purpose", "incident-response for api-gateway")

        # Use the scope-bound token to rollback api-gateway
        print("\n      Using rollback-only token to rollback api-gateway to v2.3.0:")
        print_action("POST", "/anip/invoke/rollback_deployment (api-gateway -> v2.3.0)")
        result = self._post(
            "/anip/invoke/rollback_deployment",
            json_body={"parameters": {"service_name": "api-gateway", "target_version": "v2.3.0"}},
            headers=self._auth_jwt(self.rollback_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        rb = result["result"]
        print_kv("rollback_id", rb["rollback_id"])
        print_kv("service_name", rb["service_name"])
        print_kv("from_version", rb["from_version"])
        print_kv("to_version", rb["to_version"])
        print_kv("status", rb["status"])

        # Show that this token CANNOT scale (scope is infra.deploy, not infra.write)
        print("\n      Attempting scale_replicas with rollback-only token (should fail):")
        print_action("POST", "/anip/invoke/scale_replicas [rollback-only token]")
        scale_result = self._post(
            "/anip/invoke/scale_replicas",
            json_body={"parameters": {"service_name": "api-gateway", "replicas": 3}},
            headers=self._auth_jwt(self.rollback_jwt),
        )

        if scale_result.get("success"):
            print("      Unexpected success -- scope enforcement not active")
        else:
            failure = scale_result.get("failure", {})
            print_kv("failure type", failure.get("type", "?"))
            print_kv("detail", failure.get("detail", "(none)"))
            print_kv("retry", failure.get("retry", "?"))
            print("\n      Scope-bound token correctly blocked: can rollback, cannot scale.")

        # Show that this token CANNOT delete (scope is infra.deploy, not infra.admin)
        print("\n      Attempting delete_resource with rollback-only token (should fail):")
        print_action("POST", "/anip/invoke/delete_resource [rollback-only token]")
        delete_result = self._post(
            "/anip/invoke/delete_resource",
            json_body={"parameters": {"resource_type": "deployment", "resource_name": "api-gateway"}},
            headers=self._auth_jwt(self.rollback_jwt),
        )

        if delete_result.get("success"):
            print("      Unexpected success -- scope enforcement not active")
        else:
            failure = delete_result.get("failure", {})
            print_kv("failure type", failure.get("type", "?"))
            print_kv("detail", failure.get("detail", "(none)"))
            print_kv("retry", failure.get("retry", "?"))
            print("\n      Scope-bound token correctly blocked: can rollback, cannot delete.")

    # ---- Step 7: Scope Enforcement + Repeated Denials ----

    def step_7_scope_enforcement(self) -> None:
        print_header(7, "SCOPE ENFORCEMENT + REPEATED DENIALS")
        print("      CI agent (scope: infra.read + infra.write) attempts delete_resource")
        print("      three times.  delete_resource requires infra.admin — all three fail.")
        print("      With aggregation_window=60 on this service, repeated denials are")
        print("      aggregated in the audit log.\n")

        # Issue a token with read+write scope for the CI agent
        ci_token_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:ci-pipeline",
                "scope": ["infra.read", "infra.write"],
                "capability": "delete_resource",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not ci_token_resp.get("issued"):
            print_kv("ERROR", ci_token_resp)
            return
        ci_delete_jwt = ci_token_resp["token"]

        for attempt in range(1, 4):
            print(f"\n      --- Attempt {attempt}/3 ---")
            print_action("POST", "/anip/invoke/delete_resource [scope insufficient]")
            result = self._post(
                "/anip/invoke/delete_resource",
                json_body={"parameters": {"resource_type": "deployment", "resource_name": "api-gateway"}},
                headers=self._auth_jwt(ci_delete_jwt),
            )

            if result.get("success"):
                print("      Unexpected success -- scope enforcement not active")
                continue

            failure = result.get("failure", {})
            print_kv("failure type", failure.get("type", "?"))
            print_kv("detail", failure.get("detail", "(none)"))
            resolution = failure.get("resolution", {})
            if resolution:
                print_kv("resolution.action", resolution.get("action", "(none)"))
                print_kv("resolution.requires", resolution.get("requires", "(none)"))
            print_kv("retry", failure.get("retry", "?"))

        print("\n      All 3 attempts correctly denied (scope_insufficient).")
        print("      With aggregation enabled (aggregation_window=60s), these repeated")
        print("      denials would be aggregated in the audit log rather than logged")
        print("      individually.")

    # ---- Step 8: Audit + Health ----

    def step_8_audit_and_health(self) -> None:
        print_header(8, "AUDIT + HEALTH")

        # Issue a token for audit query
        print_action("POST", "/anip/tokens (audit query token)")
        audit_token_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:audit-reader",
                "scope": ["infra.read", "infra.write", "infra.deploy", "infra.admin"],
                "capability": "list_deployments",
            },
            headers=self._auth_api_key(self.API_KEY_PLATFORM),
        )
        if not audit_token_resp.get("issued"):
            print_kv("ERROR", audit_token_resp)
            return
        audit_jwt = audit_token_resp["token"]

        print_action("POST", "/anip/audit")
        audit = self._post(
            "/anip/audit",
            headers=self._auth_jwt(audit_jwt),
        )

        entries = audit.get("entries", [])
        print_kv("total entries", len(entries))

        if entries:
            print(f"\n      {'#':<4} {'Capability':<25} {'OK?':<6} {'Event Class'}")
            print(f"      {'-'*4} {'-'*25} {'-'*6} {'-'*22}")
            for i, entry in enumerate(entries[-10:], 1):
                cap = entry.get("capability", "?")
                ok = entry.get("success", "?")
                ec = entry.get("event_class", "?")
                print(f"      {i:<4} {cap:<25} {str(ok):<6} {ec}")

            # Show a detailed entry
            success_entries = [e for e in entries if e.get("success")]
            if success_entries:
                last = success_entries[-1]
                print(f"\n      Last successful invocation detail:")
                print_kv("capability", last.get("capability", "?"))
                print_kv("subject", last.get("subject", "?"))
                print_kv("root_principal", last.get("root_principal", "?"))
                print_kv("event_class", last.get("event_class", "?"))
                chain = last.get("delegation_chain", [])
                if chain:
                    print_kv("delegation_chain", " -> ".join(chain))

        # Hit the health endpoint
        print_action("GET", "/-/health")
        health = self._get("/-/health")
        for key in ("status", "service_id", "protocol", "uptime_seconds"):
            if key in health:
                print_kv(key, health[key])
        checks = health.get("checks", {})
        if checks:
            for check_name, check_val in checks.items():
                print_kv(f"check.{check_name}", check_val)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP DevOps Infrastructure Showcase Demo")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the devops showcase server (default: $BASE_URL or http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    demo = DevOpsDemo(args.base_url)
    try:
        demo.run()
    except httpx.ConnectError:
        print(f"\nError: Cannot connect to server at {args.base_url}")
        print("Start the server first: python app.py")
        sys.exit(1)
    finally:
        demo.client.close()


if __name__ == "__main__":
    main()
