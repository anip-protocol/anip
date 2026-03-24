"""Contract test runner — orchestrates probes and checks."""

from __future__ import annotations

import os

import httpx

from .checks.check_result import CheckResult
from .checks.classification import ClassificationCheck
from .checks.compensation import CompensationCheck
from .checks.cost_presence import CostPresenceCheck
from .checks.read_purity import ReadPurityCheck
from .probes.audit_probe import AuditProbe
from .probes.storage_probe import StorageProbe


class ContractTestRunner:
    """Runs all contract checks for an ANIP service."""

    def __init__(
        self,
        base_url: str,
        test_pack: dict,
        storage_dsn: str | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.test_pack = test_pack
        self.storage_probe = StorageProbe(storage_dsn) if storage_dsn else None

    async def run_all(self) -> list[CheckResult]:
        """Execute the full contract test suite and return results."""
        results: list[CheckResult] = []

        # 1. Fetch manifest.
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/anip/manifest")
            resp.raise_for_status()
            manifest = resp.json()

        raw_caps = manifest.get("capabilities", {})
        if isinstance(raw_caps, dict):
            cap_by_name: dict[str, dict] = raw_caps
        else:
            cap_by_name = {c["name"]: c for c in raw_caps}

        # 2. Resolve credentials from test pack.
        creds = self.test_pack.get("credentials", {})
        api_key = os.environ.get(
            creds.get("api_key_env", "ANIP_TEST_API_KEY"),
            creds.get("api_key_default", "demo-agent-key"),
        )

        # 3. Per-capability checks.
        samples = self.test_pack.get("samples", {})
        for cap_name, sample_inputs in samples.items():
            declaration = cap_by_name.get(cap_name)
            if declaration is None:
                results.append(
                    CheckResult(
                        check_name="manifest_lookup",
                        capability=cap_name,
                        result="SKIP",
                        confidence="medium",
                        detail=f"Capability '{cap_name}' not found in manifest",
                    )
                )
                continue

            # 3a. Issue token.
            async with httpx.AsyncClient() as client:
                token_resp = await client.post(
                    f"{self.base_url}/anip/tokens",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={
                        "capability": cap_name,
                        "scope": declaration.get("minimum_scope", []),
                    },
                )
                if token_resp.status_code != 200:
                    results.append(
                        CheckResult(
                            check_name="token_issue",
                            capability=cap_name,
                            result="FAIL",
                            confidence="medium",
                            detail=f"Token issuance failed: {token_resp.status_code}",
                        )
                    )
                    continue
                token_data = token_resp.json()
                bearer = token_data.get("token", token_data.get("access_token", ""))

            # 3b. Storage probe: before-snapshot.
            before_snapshot = None
            if self.storage_probe:
                before_snapshot = self.storage_probe.snapshot()

            # 3c. Invoke capability.
            async with httpx.AsyncClient() as client:
                invoke_resp = await client.post(
                    f"{self.base_url}/anip/invoke/{cap_name}",
                    headers={"Authorization": f"Bearer {bearer}"},
                    json=sample_inputs,
                )

            invoke_data = invoke_resp.json() if invoke_resp.status_code == 200 else {}

            # 3d. Storage probe: after-snapshot + compare.
            storage_findings = None
            if self.storage_probe and before_snapshot is not None:
                after_snapshot = self.storage_probe.snapshot()
                storage_findings = self.storage_probe.compare(
                    before_snapshot, after_snapshot
                )

            # 3e. Audit probe: query latest entry.
            audit_entry = None
            audit_probe = AuditProbe(self.base_url, bearer)
            try:
                entries = await audit_probe.query_latest(cap_name, limit=1)
                if entries:
                    audit_entry = entries[0]
            except httpx.HTTPStatusError:
                pass  # Audit may not be available.

            # 3f. Run applicable checks.
            if ReadPurityCheck.applies(declaration):
                results.append(
                    ReadPurityCheck.run(cap_name, audit_entry, storage_findings)
                )

            if ClassificationCheck.applies(declaration):
                results.append(
                    ClassificationCheck.run(cap_name, declaration, audit_entry)
                )

            if CostPresenceCheck.applies(declaration):
                results.append(CostPresenceCheck.run(cap_name, invoke_data))

        # 4. Compensation scenarios.
        for scenario in self.test_pack.get("compensation_scenarios", []):
            if CompensationCheck.applies(scenario):
                results.append(
                    await CompensationCheck.run(
                        self.base_url, api_key, scenario, cap_by_name,
                    )
                )

        return results
