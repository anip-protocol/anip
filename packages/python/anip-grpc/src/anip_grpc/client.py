"""ANIP gRPC transport client — typed methods over a gRPC channel."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Iterator

# Ensure generated stubs can resolve `from anip.v1 import anip_pb2`
_generated_dir = str(Path(__file__).parent / "generated")
if _generated_dir not in sys.path:
    sys.path.insert(0, _generated_dir)

import grpc  # noqa: E402

from anip_grpc.generated.anip.v1 import anip_pb2  # noqa: E402
from anip_grpc.generated.anip.v1 import anip_pb2_grpc  # noqa: E402


class AnipGrpcClient:
    """gRPC client for the ANIP protocol.

    Wraps a gRPC channel and exposes typed methods that return plain dicts.
    Supports use as a context manager.
    """

    def __init__(self, target: str) -> None:
        """Connect to an ANIP gRPC server.

        Args:
            target: gRPC target string, e.g. "localhost:50051".
        """
        self._channel = grpc.insecure_channel(target)
        self._stub = anip_pb2_grpc.AnipServiceStub(self._channel)

    def close(self) -> None:
        """Close the underlying gRPC channel."""
        self._channel.close()

    def __enter__(self) -> "AnipGrpcClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Public (no auth)
    # ------------------------------------------------------------------

    def discovery(self) -> dict:
        """Call Discovery and return the parsed response dict."""
        resp = self._stub.Discovery(anip_pb2.DiscoveryRequest())
        return json.loads(resp.json)

    def manifest(self) -> dict:
        """Call Manifest and return ``{"manifest": dict, "signature": str}``."""
        resp = self._stub.Manifest(anip_pb2.ManifestRequest())
        return {
            "manifest": json.loads(resp.manifest_json),
            "signature": resp.signature,
        }

    def jwks(self) -> dict:
        """Call Jwks and return the parsed JWKS dict."""
        resp = self._stub.Jwks(anip_pb2.JwksRequest())
        return json.loads(resp.json)

    def list_checkpoints(self, limit: int = 10) -> dict:
        """Call ListCheckpoints and return the parsed response dict."""
        resp = self._stub.ListCheckpoints(
            anip_pb2.ListCheckpointsRequest(limit=limit)
        )
        return json.loads(resp.json)

    def get_checkpoint(self, id: str, **kwargs) -> dict:
        """Call GetCheckpoint and return the parsed response dict.

        Keyword args:
            include_proof (bool): Include Merkle proof.
            leaf_index (int): Leaf index for inclusion proof.
            consistency_from (int): Tree size to prove consistency from.
        """
        req = anip_pb2.GetCheckpointRequest(id=id)
        if kwargs.get("include_proof"):
            req.include_proof = True
        if kwargs.get("leaf_index") is not None:
            req.leaf_index = kwargs["leaf_index"]
        if kwargs.get("consistency_from") is not None:
            req.consistency_from = kwargs["consistency_from"]
        resp = self._stub.GetCheckpoint(req)
        return json.loads(resp.json)

    # ------------------------------------------------------------------
    # Bootstrap or JWT auth
    # ------------------------------------------------------------------

    def issue_token(
        self,
        bearer: str,
        subject: str,
        scope: list[str],
        capability: str,
        **kwargs,
    ) -> dict:
        """Call IssueToken and return the parsed response dict.

        Args:
            bearer: API key or existing JWT for authentication.
            subject: Token subject (e.g. "agent:my-agent").
            scope: List of scope strings.
            capability: The target capability.

        Keyword args:
            purpose_parameters (dict): Additional purpose parameters (JSON-encoded).
            parent_token (str): Parent token for delegation.
            ttl_hours (float): Token TTL in hours.
            caller_class (str): Caller classification string.
        """
        req = anip_pb2.IssueTokenRequest(
            subject=subject,
            scope=scope,
            capability=capability,
        )
        if kwargs.get("purpose_parameters") is not None:
            req.purpose_parameters_json = json.dumps(kwargs["purpose_parameters"])
        if kwargs.get("parent_token"):
            req.parent_token = kwargs["parent_token"]
        if kwargs.get("ttl_hours") is not None:
            req.ttl_hours = kwargs["ttl_hours"]
        if kwargs.get("caller_class"):
            req.caller_class = kwargs["caller_class"]

        resp = self._stub.IssueToken(
            req,
            metadata=[("authorization", f"Bearer {bearer}")],
        )
        result: dict = {"issued": resp.issued}
        if resp.token:
            result["token"] = resp.token
        if resp.token_id:
            result["token_id"] = resp.token_id
        if resp.expires:
            result["expires"] = resp.expires
        if resp.HasField("failure"):
            result["failure"] = {
                "type": resp.failure.type,
                "detail": resp.failure.detail,
                "retry": resp.failure.retry,
            }
            if resp.failure.resolution_json:
                result["failure"]["resolution"] = json.loads(resp.failure.resolution_json)
        return result

    # ------------------------------------------------------------------
    # JWT auth
    # ------------------------------------------------------------------

    def permissions(self, bearer: str) -> dict:
        """Call Permissions and return the parsed response dict.

        Args:
            bearer: JWT bearer token.
        """
        resp = self._stub.Permissions(
            anip_pb2.PermissionsRequest(),
            metadata=[("authorization", f"Bearer {bearer}")],
        )
        result: dict = {"success": resp.success}
        if resp.json:
            result.update(json.loads(resp.json))
        return result

    def invoke(
        self,
        bearer: str,
        capability: str,
        parameters: dict,
        client_reference_id: str | None = None,
    ) -> dict:
        """Call Invoke and return the parsed response dict.

        Args:
            bearer: JWT bearer token.
            capability: Capability name to invoke.
            parameters: Input parameters dict.
            client_reference_id: Optional client-side correlation ID.
        """
        req = anip_pb2.InvokeRequest(
            capability=capability,
            parameters_json=json.dumps(parameters),
            client_reference_id=client_reference_id or "",
        )
        resp = self._stub.Invoke(
            req,
            metadata=[("authorization", f"Bearer {bearer}")],
        )
        result: dict = {
            "success": resp.success,
            "invocation_id": resp.invocation_id,
            "client_reference_id": resp.client_reference_id,
        }
        if resp.success:
            if resp.result_json:
                result["result"] = json.loads(resp.result_json)
            if resp.cost_actual_json:
                result["cost_actual"] = json.loads(resp.cost_actual_json)
        else:
            if resp.HasField("failure"):
                result["failure"] = {
                    "type": resp.failure.type,
                    "detail": resp.failure.detail,
                    "retry": resp.failure.retry,
                }
                if resp.failure.resolution_json:
                    result["failure"]["resolution"] = json.loads(resp.failure.resolution_json)
        return result

    def invoke_stream(
        self,
        bearer: str,
        capability: str,
        parameters: dict,
        client_reference_id: str | None = None,
    ) -> Iterator[dict]:
        """Call InvokeStream and yield event dicts.

        Each yielded dict has a ``type`` key:
        - ``"progress"``: intermediate event with ``payload`` (dict) and ``invocation_id``.
        - ``"completed"``: terminal success with ``invocation_id``, ``client_reference_id``,
          ``result`` (dict), and optional ``cost_actual``.
        - ``"failed"``: terminal failure with ``invocation_id``, ``client_reference_id``,
          and ``failure`` dict.

        Args:
            bearer: JWT bearer token.
            capability: Capability name to invoke.
            parameters: Input parameters dict.
            client_reference_id: Optional client-side correlation ID.
        """
        req = anip_pb2.InvokeRequest(
            capability=capability,
            parameters_json=json.dumps(parameters),
            client_reference_id=client_reference_id or "",
        )
        stream = self._stub.InvokeStream(
            req,
            metadata=[("authorization", f"Bearer {bearer}")],
        )
        for event in stream:
            if event.HasField("progress"):
                p = event.progress
                yield {
                    "type": "progress",
                    "invocation_id": p.invocation_id,
                    "payload": json.loads(p.payload_json) if p.payload_json else {},
                }
            elif event.HasField("completed"):
                c = event.completed
                entry: dict = {
                    "type": "completed",
                    "invocation_id": c.invocation_id,
                    "client_reference_id": c.client_reference_id,
                }
                if c.result_json:
                    entry["result"] = json.loads(c.result_json)
                if c.cost_actual_json:
                    entry["cost_actual"] = json.loads(c.cost_actual_json)
                yield entry
            elif event.HasField("failed"):
                f = event.failed
                failure: dict = {
                    "type": f.failure.type,
                    "detail": f.failure.detail,
                    "retry": f.failure.retry,
                }
                if f.failure.resolution_json:
                    failure["resolution"] = json.loads(f.failure.resolution_json)
                yield {
                    "type": "failed",
                    "invocation_id": f.invocation_id,
                    "client_reference_id": f.client_reference_id,
                    "failure": failure,
                }

    def query_audit(self, bearer: str, **kwargs) -> dict:
        """Call QueryAudit and return the parsed response dict.

        Args:
            bearer: JWT bearer token.

        Keyword args:
            capability (str): Filter by capability.
            since (str): ISO timestamp lower bound.
            invocation_id (str): Filter by invocation ID.
            client_reference_id (str): Filter by client reference ID.
            event_class (str): Filter by event class.
            limit (int): Maximum number of entries.
        """
        req = anip_pb2.QueryAuditRequest()
        if kwargs.get("capability"):
            req.capability = kwargs["capability"]
        if kwargs.get("since"):
            req.since = kwargs["since"]
        if kwargs.get("invocation_id"):
            req.invocation_id = kwargs["invocation_id"]
        if kwargs.get("client_reference_id"):
            req.client_reference_id = kwargs["client_reference_id"]
        if kwargs.get("event_class"):
            req.event_class = kwargs["event_class"]
        if kwargs.get("limit") is not None:
            req.limit = kwargs["limit"]

        resp = self._stub.QueryAudit(
            req,
            metadata=[("authorization", f"Bearer {bearer}")],
        )
        result: dict = {"success": resp.success}
        if resp.json:
            result.update(json.loads(resp.json))
        if not resp.success and resp.HasField("failure"):
            result["failure"] = {
                "type": resp.failure.type,
                "detail": resp.failure.detail,
                "retry": resp.failure.retry,
            }
        return result
