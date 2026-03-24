"""compensation check — executes a setup + compensate flow from test packs."""

from __future__ import annotations

import httpx

from .check_result import CheckResult


class CompensationCheck:
    """Only runs when the test pack provides ``compensation_scenarios``."""

    name = "compensation"

    @staticmethod
    def applies(scenario: dict | None) -> bool:
        return scenario is not None

    @staticmethod
    async def run(
        base_url: str,
        bearer: str,
        scenario: dict,
    ) -> CheckResult:
        """Execute a compensation scenario.

        A scenario dict contains:
        - ``setup_capability``: capability name for the initial action
        - ``setup_params``: parameters for the setup invocation
        - ``extract_fields``: list of fields to pull from setup response
        - ``compensate_capability``: capability to invoke for compensation
        - ``compensate_params_template``: dict with ``{field}`` placeholders
        """
        base_url = base_url.rstrip("/")
        headers = {"Authorization": f"Bearer {bearer}"}

        setup_cap = scenario["setup_capability"]
        compensate_cap = scenario["compensate_capability"]

        async with httpx.AsyncClient() as client:
            # Step 1: Invoke setup capability.
            setup_resp = await client.post(
                f"{base_url}/anip/invoke/{setup_cap}",
                headers=headers,
                json=scenario.get("setup_params", {}),
            )
            if setup_resp.status_code != 200:
                return CheckResult(
                    check_name="compensation",
                    capability=compensate_cap,
                    result="FAIL",
                    confidence="medium",
                    detail=(
                        f"Setup invocation '{setup_cap}' failed: "
                        f"{setup_resp.status_code} {setup_resp.text}"
                    ),
                )

            setup_data = setup_resp.json()
            result_data = setup_data.get("result", setup_data)

            # Step 2: Extract fields from setup response.
            extracted: dict[str, str] = {}
            for field in scenario.get("extract_fields", []):
                value = result_data.get(field)
                if value is None:
                    return CheckResult(
                        check_name="compensation",
                        capability=compensate_cap,
                        result="FAIL",
                        confidence="medium",
                        detail=f"Field '{field}' not found in setup response",
                    )
                extracted[field] = str(value)

            # Step 3: Build compensation params from template.
            template = scenario.get("compensate_params_template", {})
            comp_params: dict[str, str] = {}
            for key, val in template.items():
                if isinstance(val, str) and val.startswith("{") and val.endswith("}"):
                    field_name = val[1:-1]
                    comp_params[key] = extracted.get(field_name, val)
                else:
                    comp_params[key] = val

            # Step 4: Invoke compensation capability.
            comp_resp = await client.post(
                f"{base_url}/anip/invoke/{compensate_cap}",
                headers=headers,
                json=comp_params,
            )
            if comp_resp.status_code != 200:
                return CheckResult(
                    check_name="compensation",
                    capability=compensate_cap,
                    result="FAIL",
                    confidence="medium",
                    detail=(
                        f"Compensation invocation '{compensate_cap}' failed: "
                        f"{comp_resp.status_code} {comp_resp.text}"
                    ),
                )

        return CheckResult(
            check_name="compensation",
            capability=compensate_cap,
            result="PASS",
            confidence="medium",
            detail=f"Compensation succeeded: {setup_cap} -> {compensate_cap}",
        )
