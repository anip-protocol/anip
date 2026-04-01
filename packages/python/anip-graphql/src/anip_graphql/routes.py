"""ANIP GraphQL bindings — mount a GraphQL endpoint on a FastAPI app."""
from __future__ import annotations

from typing import Any

from ariadne import QueryType, MutationType, ScalarType, make_executable_schema
from ariadne.asgi import GraphQL
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from anip_service import ANIPService, ANIPError
from .translation import (
    generate_schema,
    build_graphql_response,
    to_camel_case,
    to_snake_case,
)


async def _resolve_auth(request, service: ANIPService, capability_name: str):
    """Resolve auth — JWT first, then API key."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    bearer = auth[7:].strip()

    # Try as JWT first — preserves original delegation chain
    jwt_error = None
    try:
        return await service.resolve_bearer_token(bearer)
    except ANIPError as e:
        jwt_error = e

    # Try as API key — only if JWT failed
    principal = await service.authenticate_bearer(bearer)
    if principal:
        cap_decl = service.get_capability_declaration(capability_name)
        min_scope = cap_decl.minimum_scope if cap_decl else []
        token_result = await service.issue_token(principal, {
            "subject": "adapter:anip-graphql",
            "scope": min_scope if min_scope else ["*"],
            "capability": capability_name,
            "purpose_parameters": {"source": "graphql"},
        })
        return await service.resolve_bearer_token(token_result["token"])

    # Surface the original JWT error
    if jwt_error:
        raise jwt_error
    return None


def _make_resolver(capability_name: str, service: ANIPService):
    """Create a resolver for a given capability."""

    async def resolver(_obj: Any, info: Any, **kwargs: Any) -> dict[str, Any]:
        # Convert camelCase args back to snake_case
        arguments = {to_snake_case(k): v for k, v in kwargs.items()}

        try:
            token = await _resolve_auth(info.context["request"], service, capability_name)
        except ANIPError as e:
            return build_graphql_response({
                "success": False,
                "failure": {
                    "type": e.error_type,
                    "detail": e.detail,
                    "resolution": e.resolution,
                    "retry": e.retry,
                },
            })

        if token is None:
            return build_graphql_response({
                "success": False,
                "failure": {
                    "type": "authentication_required",
                    "detail": "Authorization header required",
                    "resolution": {"action": "provide_credentials", "recovery_class": "retry_now"},
                    "retry": True,
                },
            })

        try:
            result = await service.invoke(capability_name, token, arguments)
        except ANIPError as e:
            return build_graphql_response({
                "success": False,
                "failure": {
                    "type": e.error_type,
                    "detail": e.detail,
                    "resolution": e.resolution,
                    "retry": e.retry,
                },
            })

        return build_graphql_response(result)

    return resolver


def mount_anip_graphql(
    app: FastAPI,
    service: ANIPService,
    *,
    path: str = "/graphql",
    prefix: str = "",
    debug: bool = False,
) -> None:
    """Mount a GraphQL endpoint on a FastAPI app.

    Args:
        app: FastAPI app instance.
        service: ANIPService to expose.
        path: GraphQL endpoint path. Default: "/graphql".
        prefix: URL prefix.
    """
    manifest = service.get_manifest()
    capabilities = {}
    for name in manifest.capabilities:
        decl = service.get_capability_declaration(name)
        if decl:
            capabilities[name] = decl

    schema_sdl = generate_schema(capabilities)

    # Build Ariadne resolvers
    query = QueryType()
    mutation = MutationType()
    json_scalar = ScalarType("JSON")

    @json_scalar.serializer
    def serialize_json(value):
        return value

    @json_scalar.value_parser
    def parse_json_value(value):
        return value

    for name, decl in capabilities.items():
        camel_name = to_camel_case(name)
        resolver_fn = _make_resolver(name, service)
        se_type = decl.side_effect.type.value if hasattr(decl.side_effect.type, "value") else str(decl.side_effect.type)
        if se_type == "read":
            query.field(camel_name)(resolver_fn)
        else:
            mutation.field(camel_name)(resolver_fn)

    schema = make_executable_schema(schema_sdl, query, mutation, json_scalar)
    graphql_app = GraphQL(schema, debug=debug)

    full_path = f"{prefix}{path}"
    app.mount(full_path, graphql_app)

    @app.get(f"{prefix}/schema.graphql")
    async def get_schema() -> PlainTextResponse:
        return PlainTextResponse(schema_sdl, media_type="text/plain")
