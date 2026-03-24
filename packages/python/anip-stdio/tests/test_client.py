"""Tests for ANIP stdio client."""
import os
import sys

import pytest

from anip_stdio.client import AnipStdioClient

SERVE_SCRIPT = os.path.join(os.path.dirname(__file__), "_serve_fixture.py")


@pytest.mark.asyncio
async def test_discovery():
    async with AnipStdioClient(sys.executable, SERVE_SCRIPT) as client:
        result = await client.discovery()
        assert "anip_discovery" in result
        assert result["anip_discovery"]["protocol"] == "anip/0.11"


@pytest.mark.asyncio
async def test_manifest():
    async with AnipStdioClient(sys.executable, SERVE_SCRIPT) as client:
        result = await client.manifest()
        assert "manifest" in result
        assert "signature" in result


@pytest.mark.asyncio
async def test_jwks():
    async with AnipStdioClient(sys.executable, SERVE_SCRIPT) as client:
        result = await client.jwks()
        assert "keys" in result


@pytest.mark.asyncio
async def test_full_flow():
    async with AnipStdioClient(sys.executable, SERVE_SCRIPT) as client:
        # Issue token
        tok = await client.issue_token(
            "test-key", subject="agent:bot", scope=["test"], capability="echo",
        )
        assert tok["issued"] is True
        jwt = tok["token"]

        # Invoke
        result = await client.invoke(jwt, "echo", {"message": "hello stdio"})
        assert result["success"] is True
        assert result["result"]["message"] == "hello stdio"

        # Permissions
        perms = await client.permissions(jwt)
        assert "available" in perms

        # Audit
        audit = await client.audit_query(jwt, capability="echo")
        assert len(audit["entries"]) > 0

        # Checkpoints
        cps = await client.checkpoints_list()
        assert "checkpoints" in cps


@pytest.mark.asyncio
async def test_auth_error():
    async with AnipStdioClient(sys.executable, SERVE_SCRIPT) as client:
        with pytest.raises(Exception, match="32001|auth|Auth"):
            await client.invoke("bad-token", "echo", {"message": "fail"})
