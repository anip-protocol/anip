#!/usr/bin/env python3
"""Financial Operations Showcase Demo — 8-step scripted ANIP interaction.

A deterministic walkthrough of ANIP governance and compliance features
using the financial operations showcase app.  Not an autonomous agent
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
# Formatting helpers (matches travel demo style)
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

class FinanceDemo:
    """Eight-step scripted ANIP interaction against the finance showcase."""

    API_KEY_COMPLIANCE = "compliance-key"
    API_KEY_TRADER = "trader-key"
    API_KEY_PARTNER = "partner-key"

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.client = httpx.Client(base_url=self.base_url, timeout=10)

        # State accumulated across steps
        self.compliance_token_id: str = ""
        self.compliance_jwt: str = ""
        self.trader_token_id: str = ""
        self.trader_jwt: str = ""
        self.exec_agent_jwt: str = ""

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
        print("ANIP Financial Operations Showcase")
        print(f"Server: {self.base_url}")
        print(f"Compliance key: {self.API_KEY_COMPLIANCE} -> human:compliance-officer@example.com")
        print(f"Trader key:     {self.API_KEY_TRADER} -> human:trader@example.com")
        print(f"Partner key:    {self.API_KEY_PARTNER} -> partner:external-fund@example.com")

        steps = [
            self.step_1_discovery,
            self.step_2_multi_hop_delegation,
            self.step_3_portfolio_query,
            self.step_4_market_data,
            self.step_5_trade_execution,
            self.step_6_disclosure_policy,
            self.step_7_audit_retention,
            self.step_8_checkpoint_proof,
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
        print("  1. Discovery — capability advertisement with side effects and trust level")
        print("  2. Multi-hop delegation — compliance -> trader -> execution agent")
        print("  3. Portfolio query — read-only capability invocation")
        print("  4. Market data — real-time data with cost signaling")
        print("  5. Trade execution — irreversible action with cost_actual tracking")
        print("  6. Disclosure policy — same failure, three different views by caller class")
        print("  7. Audit with retention tiers — event classification and tiered retention")
        print("  8. Checkpoint proofs — Merkle-tree anchoring for tamper evidence")

    # ---- Step 1: Discovery ----

    def step_1_discovery(self) -> None:
        print_header(1, "DISCOVERY")
        print_action("GET", "/.well-known/anip")

        disco = self._get("/.well-known/anip")
        anip = disco["anip_discovery"]

        print_kv("protocol", anip["protocol"])
        print_kv("compliance", anip["compliance"])
        print_kv("trust_level", anip["trust_level"])

        # Show disclosure posture
        posture = anip.get("posture", {})
        fd = posture.get("failure_disclosure", {})
        print_kv("disclosure_level", fd.get("detail_level", "?"))
        print_kv("caller_classes", fd.get("caller_classes", "?"))

        # Fetch manifest for side-effect info
        manifest = self._get("/anip/manifest")
        print("\n      Capabilities and side effects:")
        for cap_name in anip["capabilities"]:
            cap = manifest["capabilities"].get(cap_name, {})
            se = cap.get("side_effect", {})
            se_type = se.get("type", "unknown") if isinstance(se, dict) else se
            scope = cap.get("minimum_scope", [])
            print(f"        - {cap_name:20s}  side_effect={se_type:15s}  scope={scope}")

    # ---- Step 2: Multi-hop Delegation ----

    def step_2_multi_hop_delegation(self) -> None:
        print_header(2, "MULTI-HOP DELEGATION")

        # Hop 1: Compliance officer issues broad token
        print("      Hop 1: Compliance officer -> broad token (read + trade + transfer)")
        print_action("POST", "/anip/tokens (compliance: broad)")
        compliance_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "human:trader@example.com",
                "scope": ["finance.read", "finance.trade", "finance.transfer"],
                "capability": "execute_trade",
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_COMPLIANCE),
        )
        if not compliance_resp.get("issued"):
            print_kv("ERROR", compliance_resp)
            return
        self.compliance_token_id = compliance_resp["token_id"]
        self.compliance_jwt = compliance_resp["token"]
        print_kv("token_id", self.compliance_token_id)
        print_kv("scope", "finance.read, finance.trade, finance.transfer")
        print_kv("delegated_to", "human:trader@example.com")

        # Hop 2: Trader narrows own authority (drops transfer, caps trade)
        print("\n      Hop 2: Trader narrows own authority (read + trade:max_$50000)")
        print_action("POST", "/anip/tokens (trader: self-narrowing via parent)")
        trader_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "human:trader@example.com",
                "scope": ["finance.read", "finance.trade:max_50000"],
                "capability": "execute_trade",
                "parent_token": self.compliance_token_id,
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_TRADER),
        )
        if not trader_resp.get("issued"):
            print_kv("ERROR", trader_resp)
            return
        self.trader_token_id = trader_resp["token_id"]
        self.trader_jwt = trader_resp["token"]
        print_kv("token_id", self.trader_token_id)
        print_kv("scope", "finance.read, finance.trade:max_$50000")
        print_kv("subject", "human:trader@example.com (self-narrowed)")

        # Hop 3: Trader delegates to execution agent with further narrowing
        print("\n      Hop 3: Trader -> execution agent (trade:max_$10000)")
        print_action("POST", "/anip/tokens (delegation to execution-bot)")
        exec_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:execution-bot",
                "scope": ["finance.read", "finance.trade:max_10000"],
                "capability": "execute_trade",
                "parent_token": self.trader_token_id,
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_TRADER),
        )
        if not exec_resp.get("issued"):
            print_kv("ERROR", exec_resp)
            return
        self.exec_agent_jwt = exec_resp["token"]
        print_kv("token_id", exec_resp["token_id"])
        print_kv("scope", "finance.read, finance.trade:max_$10000")
        print_kv("delegated_to", "agent:execution-bot")

        print("\n      Hierarchy: compliance-officer -> trader (read+trade:$50k)")
        print("                   -> execution-bot (read+trade:$10k)")

    # ---- Step 3: Portfolio Query ----

    def step_3_portfolio_query(self) -> None:
        print_header(3, "PORTFOLIO QUERY")

        # Issue a read-only token for portfolio query
        print_action("POST", "/anip/tokens (read-only for query_portfolio)")
        read_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:execution-bot",
                "scope": ["finance.read"],
                "capability": "query_portfolio",
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_COMPLIANCE),
        )
        if not read_resp.get("issued"):
            print_kv("ERROR", read_resp)
            return
        read_jwt = read_resp["token"]

        print_action("POST", "/anip/invoke/query_portfolio")
        result = self._post(
            "/anip/invoke/query_portfolio",
            json_body={"parameters": {}},
            headers=self._auth_jwt(read_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        holdings = result["result"]["holdings"]
        total = result["result"]["total_value"]
        print_kv("total_value", f"${total:,.2f}")
        print_kv("holdings", len(holdings))
        print(f"\n      {'Symbol':<8} {'Shares':>8} {'Price':>10} {'Value':>12}")
        print(f"      {'-'*8} {'-'*8} {'-'*10} {'-'*12}")
        for h in holdings:
            print(f"      {h['symbol']:<8} {h['shares']:>8} ${h['current_price']:>9.2f} ${h['market_value']:>11,.2f}")

    # ---- Step 4: Market Data ----

    def step_4_market_data(self) -> None:
        print_header(4, "MARKET DATA")

        # Issue a read-only token for market data
        print_action("POST", "/anip/tokens (read-only for get_market_data)")
        md_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:execution-bot",
                "scope": ["finance.read"],
                "capability": "get_market_data",
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_COMPLIANCE),
        )
        if not md_resp.get("issued"):
            print_kv("ERROR", md_resp)
            return
        md_jwt = md_resp["token"]

        print_action("POST", "/anip/invoke/get_market_data (AAPL)")
        result = self._post(
            "/anip/invoke/get_market_data",
            json_body={"parameters": {"symbol": "AAPL"}},
            headers=self._auth_jwt(md_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        md = result["result"]
        print_kv("symbol", md["symbol"])
        print_kv("bid", f"${md['bid']:.2f}")
        print_kv("ask", f"${md['ask']:.2f}")
        print_kv("last", f"${md['last']:.2f}")
        print_kv("spread", f"${md['spread']:.2f}")
        print_kv("volume", f"{md['volume']:,}")

    # ---- Step 5: Trade Execution ----

    def step_5_trade_execution(self) -> None:
        print_header(5, "TRADE EXECUTION")

        print(f"\n      Executing buy: 10 shares of AAPL using execution-agent token")
        print_action("POST", "/anip/invoke/execute_trade (AAPL, buy, 10)")
        result = self._post(
            "/anip/invoke/execute_trade",
            json_body={"parameters": {"symbol": "AAPL", "side": "buy", "quantity": 10}},
            headers=self._auth_jwt(self.exec_agent_jwt),
        )

        if not result.get("success"):
            print_kv("FAILURE", result.get("failure", result))
            return

        trade = result["result"]
        print_kv("trade_id", trade["trade_id"])
        print_kv("symbol", trade["symbol"])
        print_kv("side", trade["side"])
        print_kv("quantity", trade["quantity"])
        print_kv("price", f"${trade['price']:.2f}")
        print_kv("fee", f"${trade['fee']:.2f}")
        print_kv("total_cost", f"${trade['total_cost']:.2f}")

        cost_actual = result.get("cost_actual", {})
        if cost_actual:
            fin = cost_actual.get("financial", {})
            print_kv("cost_actual", f"${fin.get('amount', '?')} {fin.get('currency', '')}")

    # ---- Step 6: Disclosure Policy Demo ----

    def step_6_disclosure_policy(self) -> None:
        print_header(6, "DISCLOSURE POLICY (centerpiece)")
        print("      Same failure, three different views based on caller class.")
        print("      Attempting execute_trade with a read-only token (scope_insufficient).\n")
        print("      Policy: internal=full, partner=reduced, default=redacted")

        # Issue three read-only tokens with different caller_class values,
        # each bound to execute_trade (which requires finance.trade scope).
        # This will produce scope_insufficient failures with different
        # disclosure levels.

        # Three tokens with different caller_class values:
        #   internal -> full disclosure
        #   partner  -> reduced disclosure (grantable_by redacted)
        #   (none)   -> redacted disclosure (generic detail, resolution stripped)
        labels = [
            ("compliance-key", "internal", self.API_KEY_COMPLIANCE),
            ("partner-key", "partner", self.API_KEY_PARTNER),
            ("trader-key", None, self.API_KEY_TRADER),
        ]

        for label, caller_class, api_key in labels:
            # Issue a read-only token bound to execute_trade capability
            # The scope is finance.read but execute_trade requires finance.trade
            token_body: dict = {
                "subject": f"agent:demo-{label}",
                "scope": ["finance.read"],
                "capability": "execute_trade",
            }
            if caller_class is not None:
                token_body["caller_class"] = caller_class
            token_resp = self._post(
                "/anip/tokens",
                json_body=token_body,
                headers=self._auth_api_key(api_key),
            )
            if not token_resp.get("issued"):
                print_kv(f"{label} token ERROR", token_resp)
                continue
            token_jwt = token_resp["token"]

            class_label = caller_class or "default"
            print(f"\n      --- {label} (caller_class={class_label}) ---")
            print_action("POST", "/anip/invoke/execute_trade [read-only token]")
            result = self._post(
                "/anip/invoke/execute_trade",
                json_body={"parameters": {"symbol": "AAPL", "side": "buy", "quantity": 5}},
                headers=self._auth_jwt(token_jwt),
            )

            if result.get("success"):
                print("      Unexpected success — scope enforcement not active")
                continue

            failure = result.get("failure", {})
            print_kv("failure type", failure.get("type", "?"))
            print_kv("detail", failure.get("detail", "(none)"))
            resolution = failure.get("resolution", {})
            if resolution:
                print_kv("resolution.action", resolution.get("action", "(none)"))
                print_kv("resolution.requires", resolution.get("requires", "(none)"))
                print_kv("resolution.grantable_by", resolution.get("grantable_by", "(none)"))
            else:
                print_kv("resolution", "(not disclosed)")
            print_kv("retry", failure.get("retry", "?"))

        print("\n      Note: internal callers see full detail and resolution;")
        print("      partner callers see reduced detail; default sees redacted.")

    # ---- Step 7: Audit with Retention Tiers ----

    def step_7_audit_retention(self) -> None:
        print_header(7, "AUDIT WITH RETENTION TIERS")

        # Use the compliance token (has broad scope) for audit query
        # Need a fresh token bound to a capability the audit endpoint accepts
        print_action("POST", "/anip/tokens (audit query token)")
        audit_token_resp = self._post(
            "/anip/tokens",
            json_body={
                "subject": "agent:audit-reader",
                "scope": ["finance.read", "finance.trade"],
                "capability": "execute_trade",
                "caller_class": "internal",
            },
            headers=self._auth_api_key(self.API_KEY_COMPLIANCE),
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
            print(f"\n      {'#':<4} {'Capability':<20} {'OK?':<6} {'Event Class':<22} {'Retention Tier'}")
            print(f"      {'-'*4} {'-'*20} {'-'*6} {'-'*22} {'-'*15}")
            for i, entry in enumerate(entries[-8:], 1):
                cap = entry.get("capability", "?")
                ok = entry.get("success", "?")
                ec = entry.get("event_class", "?")
                rt = entry.get("retention_tier", "?")
                print(f"      {i:<4} {cap:<20} {str(ok):<6} {ec:<22} {rt}")

            # Show a detailed entry
            success_entries = [e for e in entries if e.get("success")]
            if success_entries:
                last = success_entries[-1]
                print(f"\n      Last successful invocation detail:")
                print_kv("capability", last.get("capability", "?"))
                print_kv("subject", last.get("subject", "?"))
                print_kv("root_principal", last.get("root_principal", "?"))
                print_kv("event_class", last.get("event_class", "?"))
                print_kv("retention_tier", last.get("retention_tier", "?"))
                cost = last.get("cost_actual", {})
                if cost:
                    fin = cost.get("financial", {})
                    print_kv("cost_actual", f"${fin.get('amount', '?')} {fin.get('currency', '')}")
                chain = last.get("delegation_chain", [])
                if chain:
                    print_kv("delegation_chain", " -> ".join(chain))

    # ---- Step 8: Checkpoint Proof ----

    def step_8_checkpoint_proof(self) -> None:
        print_header(8, "CHECKPOINT PROOF")
        print_action("GET", "/anip/checkpoints")

        checkpoints = self._get("/anip/checkpoints")
        cp_list = checkpoints.get("checkpoints", [])
        print_kv("checkpoints found", len(cp_list))

        if not cp_list:
            print("\n      No checkpoints yet (checkpoint interval is 30s).")
            print("      In production, checkpoints provide Merkle-tree anchoring")
            print("      for tamper-evident audit logs.")
            return

        # Show the most recent checkpoint
        cp = cp_list[0]
        print(f"\n      Most recent checkpoint:")
        print_kv("checkpoint_id", cp.get("checkpoint_id", "?"))
        rng = cp.get("range", {})
        print_kv("range", f"seq {rng.get('first_sequence', '?')} - {rng.get('last_sequence', '?')}")
        print_kv("merkle_root", cp.get("merkle_root", "?"))
        print_kv("entry_count", cp.get("entry_count", "?"))
        print_kv("timestamp", cp.get("timestamp", "?"))
        print_kv("previous", cp.get("previous_checkpoint", "(none)"))

        # Fetch with proof if available
        cp_id = cp.get("checkpoint_id")
        if cp_id:
            print_action("GET", f"/anip/checkpoints/{cp_id}?include_proof=true&leaf_index=0")
            detail = self._get(f"/anip/checkpoints/{cp_id}?include_proof=true&leaf_index=0")
            proof = detail.get("inclusion_proof")
            if proof:
                print_kv("inclusion_proof.leaf_hash", proof.get("leaf_hash", "?")[:40] + "...")
                print_kv("inclusion_proof.path_length", len(proof.get("path", [])))
            elif detail.get("proof_unavailable"):
                print_kv("proof_unavailable", detail["proof_unavailable"])


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="ANIP Financial Operations Showcase Demo")
    parser.add_argument(
        "--base-url",
        default=os.getenv("BASE_URL", "http://127.0.0.1:8000"),
        help="Base URL of the finance showcase server (default: $BASE_URL or http://127.0.0.1:8000)",
    )
    args = parser.parse_args()

    demo = FinanceDemo(args.base_url)
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
