"""Tests for getHealth() runtime health reporting."""
from __future__ import annotations

import pytest

from anip_core import (
    CapabilityDeclaration,
    CapabilityInput,
    CapabilityOutput,
    SideEffect,
    SideEffectType,
)

from anip_service import ANIPService, Capability
from anip_service.hooks import HealthReport


def _test_cap(name: str = "greet") -> Capability:
    return Capability(
        declaration=CapabilityDeclaration(
            name=name,
            description="Say hello",
            contract_version="1.0",
            inputs=[CapabilityInput(name="name", type="string", required=True, description="Who to greet")],
            output=CapabilityOutput(type="object", fields=["message"]),
            side_effect=SideEffect(type=SideEffectType.READ, rollback_window="not_applicable"),
            minimum_scope=["greet"],
        ),
        handler=lambda ctx, params: {"message": f"Hello, {params['name']}!"},
    )


def _make_service(**kwargs) -> ANIPService:
    defaults = dict(
        service_id="health-test",
        capabilities=[_test_cap()],
        storage=":memory:",
    )
    defaults.update(kwargs)
    return ANIPService(**defaults)


class TestGetHealth:
    @pytest.mark.asyncio
    async def test_returns_valid_health_report_shape(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert isinstance(report, HealthReport)
            assert report.status in ("healthy", "degraded", "unhealthy")
            assert "type" in report.storage
            assert isinstance(report.retention, dict)
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_status_is_healthy_under_normal_conditions(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert report.status == "healthy"
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_checkpoint_is_none_without_policy(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert report.checkpoint is None
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_checkpoint_present_with_anchored_trust_and_policy(self):
        from anip_server import CheckpointPolicy
        service = _make_service(
            trust="anchored",
            checkpoint_policy=CheckpointPolicy(interval_seconds=300),
        )
        await service.start()
        try:
            report = service.get_health()
            assert report.checkpoint is not None
            assert "healthy" in report.checkpoint
            assert "last_run_at" in report.checkpoint
            assert "lag_seconds" in report.checkpoint
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_aggregation_is_none_without_window(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert report.aggregation is None
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_aggregation_present_with_window(self):
        service = _make_service(aggregation_window=60)
        await service.start()
        try:
            report = service.get_health()
            assert report.aggregation is not None
            assert report.aggregation["pending_windows"] == 0
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_storage_type_reflects_memory_backend(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert report.storage["type"] == "memory"
        finally:
            service.stop()

    @pytest.mark.asyncio
    async def test_retention_fields_present_with_defaults(self):
        service = _make_service()
        await service.start()
        try:
            report = service.get_health()
            assert report.retention["healthy"] is True
            assert report.retention["last_run_at"] is None
            assert report.retention["last_deleted_count"] == 0
        finally:
            service.stop()
