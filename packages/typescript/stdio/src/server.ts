/**
 * ANIP stdio transport server -- JSON-RPC 2.0 over stdin/stdout.
 */

import { createInterface } from "readline";
import type { ANIPService } from "@anip/service";
import { ANIPError } from "@anip/service";

// ---------------------------------------------------------------------------
// JSON-RPC 2.0 constants
// ---------------------------------------------------------------------------

const VALID_METHODS = new Set([
  "anip.discovery",
  "anip.manifest",
  "anip.jwks",
  "anip.tokens.issue",
  "anip.permissions",
  "anip.invoke",
  "anip.audit.query",
  "anip.checkpoints.list",
  "anip.checkpoints.get",
]);

const PARSE_ERROR = -32700;
const INVALID_REQUEST = -32600;
const METHOD_NOT_FOUND = -32601;
const AUTH_ERROR = -32001;
const SCOPE_ERROR = -32002;
const NOT_FOUND = -32004;
const INTERNAL_ERROR = -32603;

const FAILURE_TYPE_TO_CODE: Record<string, number> = {
  authentication_required: AUTH_ERROR,
  invalid_token: AUTH_ERROR,
  token_expired: AUTH_ERROR,
  scope_insufficient: SCOPE_ERROR,
  budget_exceeded: SCOPE_ERROR,
  purpose_mismatch: SCOPE_ERROR,
  unknown_capability: NOT_FOUND,
  not_found: NOT_FOUND,
  internal_error: INTERNAL_ERROR,
  unavailable: INTERNAL_ERROR,
  concurrent_lock: INTERNAL_ERROR,
};

// ---------------------------------------------------------------------------
// JSON-RPC helpers
// ---------------------------------------------------------------------------

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: string | number | null;
  result?: unknown;
  error?: { code: number; message: string; data?: Record<string, unknown> };
}

interface JsonRpcNotification {
  jsonrpc: "2.0";
  method: string;
  params: Record<string, unknown>;
}

type JsonRpcMessage = JsonRpcResponse | JsonRpcNotification;

function makeResponse(
  requestId: string | number | null,
  result: unknown,
): JsonRpcResponse {
  return { jsonrpc: "2.0", id: requestId, result };
}

function makeError(
  requestId: string | number | null,
  code: number,
  message: string,
  data?: Record<string, unknown>,
): JsonRpcResponse {
  const error: { code: number; message: string; data?: Record<string, unknown> } = {
    code,
    message,
  };
  if (data !== undefined) {
    error.data = data;
  }
  return { jsonrpc: "2.0", id: requestId, error };
}

function makeNotification(
  method: string,
  params: Record<string, unknown>,
): JsonRpcNotification {
  return { jsonrpc: "2.0", method, params };
}

// ---------------------------------------------------------------------------
// Request validation
// ---------------------------------------------------------------------------

function validateRequest(msg: Record<string, unknown>): string | null {
  if (typeof msg !== "object" || msg === null || Array.isArray(msg)) {
    return "Request must be a JSON object";
  }
  if (msg.jsonrpc !== "2.0") {
    return "Missing or invalid 'jsonrpc' field (must be '2.0')";
  }
  if (!("method" in msg)) {
    return "Missing 'method' field";
  }
  if (typeof msg.method !== "string") {
    return "'method' must be a string";
  }
  if (!("id" in msg)) {
    return "Missing 'id' field (notifications not supported as requests)";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Auth extraction
// ---------------------------------------------------------------------------

function extractAuth(params: Record<string, unknown> | undefined): string | null {
  if (params == null) return null;
  const auth = params.auth;
  if (auth == null || typeof auth !== "object" || Array.isArray(auth)) return null;
  const bearer = (auth as Record<string, unknown>).bearer;
  return typeof bearer === "string" ? bearer : null;
}

// ---------------------------------------------------------------------------
// Server
// ---------------------------------------------------------------------------

export class AnipStdioServer {
  private readonly service: ANIPService;

  constructor(service: ANIPService) {
    this.service = service;
  }

  /**
   * Validate and dispatch a JSON-RPC request to the appropriate handler.
   *
   * Returns a single JSON-RPC response, or for streaming invocations
   * an array of [notification..., response].
   */
  async handleRequest(
    msg: Record<string, unknown>,
  ): Promise<JsonRpcMessage | JsonRpcMessage[]> {
    const errorDesc = validateRequest(msg);
    if (errorDesc !== null) {
      return makeError(
        (msg.id as string | number | null) ?? null,
        INVALID_REQUEST,
        errorDesc,
      );
    }

    const requestId = msg.id as string | number | null;
    const method = msg.method as string;
    const params = (msg.params as Record<string, unknown>) ?? {};

    if (!VALID_METHODS.has(method)) {
      return makeError(requestId, METHOD_NOT_FOUND, `Unknown method: ${method}`);
    }

    const handler = this.dispatch[method];
    if (!handler) {
      return makeError(requestId, INTERNAL_ERROR, `No handler for ${method}`);
    }

    try {
      const result = await handler.call(this, params);

      // Streaming invoke returns [notifications[], finalResult]
      if (Array.isArray(result) && result.length === 2 && Array.isArray(result[0])) {
        const [notifications, finalResult] = result as [
          JsonRpcNotification[],
          Record<string, unknown>,
        ];
        const messages: JsonRpcMessage[] = [...notifications];
        messages.push(makeResponse(requestId, finalResult));
        return messages;
      }

      return makeResponse(requestId, result);
    } catch (err) {
      if (err instanceof ANIPError) {
        const code = FAILURE_TYPE_TO_CODE[err.errorType] ?? INTERNAL_ERROR;
        return makeError(requestId, code, err.detail, {
          type: err.errorType,
          detail: err.detail,
          retry: err.retry,
        });
      }
      return makeError(
        requestId,
        INTERNAL_ERROR,
        err instanceof Error ? err.message : String(err),
      );
    }
  }

  // -------------------------------------------------------------------------
  // Method handlers
  // -------------------------------------------------------------------------

  private async handleDiscovery(
    _params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return this.service.getDiscovery();
  }

  private async handleManifest(
    _params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const [bodyBytes, signature] = await this.service.getSignedManifest();
    const bodyStr =
      typeof bodyBytes === "string"
        ? bodyBytes
        : new TextDecoder().decode(bodyBytes);
    return { manifest: JSON.parse(bodyStr), signature };
  }

  private async handleJwks(
    _params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    return await this.service.getJwks();
  }

  private async handleTokensIssue(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const bearer = extractAuth(params);
    if (bearer === null) {
      throw new ANIPError("authentication_required", "This method requires auth.bearer");
    }

    // Try bootstrap auth (API key) first, then ANIP JWT
    const principal = await this.service.authenticateBearer(bearer);
    if (principal === null) {
      throw new ANIPError("invalid_token", "Bearer token not recognized");
    }

    // Build the token request body from params
    const body: Record<string, unknown> = {};
    for (const key of [
      "subject",
      "scope",
      "capability",
      "purpose_parameters",
      "parent_token",
      "ttl_hours",
      "caller_class",
    ]) {
      if (key in params) {
        body[key] = params[key];
      }
    }

    return await this.service.issueToken(principal, body);
  }

  private async handlePermissions(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const token = await this.resolveJwt(params);
    return this.service.discoverPermissions(token);
  }

  private async handleInvoke(
    params: Record<string, unknown>,
  ): Promise<
    Record<string, unknown> | [JsonRpcNotification[], Record<string, unknown>]
  > {
    const token = await this.resolveJwt(params);

    const capability = params.capability;
    if (!capability || typeof capability !== "string") {
      throw new ANIPError("unknown_capability", "Missing 'capability' in params");
    }

    const parameters = (params.parameters as Record<string, unknown>) ?? {};
    const clientReferenceId =
      (params.client_reference_id as string | undefined) ?? null;
    const stream = params.stream === true;

    if (stream) {
      const notifications: JsonRpcNotification[] = [];

      const progressSink = async (
        payload: Record<string, unknown>,
      ): Promise<void> => {
        notifications.push(
          makeNotification("anip.invoke.progress", payload),
        );
      };

      const result = await this.service.invoke(capability, token, parameters, {
        clientReferenceId,
        stream: true,
        progressSink,
      });
      return [notifications, result];
    }

    return await this.service.invoke(capability, token, parameters, {
      clientReferenceId,
    });
  }

  private async handleAuditQuery(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const token = await this.resolveJwt(params);

    const filters: Record<string, unknown> = {};
    for (const key of [
      "capability",
      "since",
      "invocation_id",
      "client_reference_id",
      "event_class",
      "limit",
    ]) {
      if (key in params) {
        filters[key] = params[key];
      }
    }

    return await this.service.queryAudit(token, filters);
  }

  private async handleCheckpointsList(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const limit = typeof params.limit === "number" ? params.limit : 10;
    return await this.service.getCheckpoints(limit);
  }

  private async handleCheckpointsGet(
    params: Record<string, unknown>,
  ): Promise<Record<string, unknown>> {
    const checkpointId = params.id;
    if (!checkpointId || typeof checkpointId !== "string") {
      throw new ANIPError("not_found", "Missing 'id' in params");
    }

    const options: Record<string, unknown> = {};
    for (const key of ["include_proof", "leaf_index", "consistency_from"]) {
      if (key in params) {
        options[key] = params[key];
      }
    }

    const result = await this.service.getCheckpoint(checkpointId, options);
    if (result === null) {
      throw new ANIPError("not_found", `Checkpoint not found: ${checkpointId}`);
    }
    return result;
  }

  // -------------------------------------------------------------------------
  // Internal helpers
  // -------------------------------------------------------------------------

  private async resolveJwt(
    params: Record<string, unknown>,
  ): Promise<ReturnType<ANIPService["resolveBearerToken"]> extends Promise<infer T> ? T : never> {
    const bearer = extractAuth(params);
    if (bearer === null) {
      throw new ANIPError(
        "authentication_required",
        "This method requires auth.bearer",
      );
    }
    return await this.service.resolveBearerToken(bearer);
  }

  // -------------------------------------------------------------------------
  // Dispatch table
  // -------------------------------------------------------------------------

  private readonly dispatch: Record<
    string,
    (params: Record<string, unknown>) => Promise<unknown>
  > = {
    "anip.discovery": this.handleDiscovery,
    "anip.manifest": this.handleManifest,
    "anip.jwks": this.handleJwks,
    "anip.tokens.issue": this.handleTokensIssue,
    "anip.permissions": this.handlePermissions,
    "anip.invoke": this.handleInvoke,
    "anip.audit.query": this.handleAuditQuery,
    "anip.checkpoints.list": this.handleCheckpointsList,
    "anip.checkpoints.get": this.handleCheckpointsGet,
  };
}

// ---------------------------------------------------------------------------
// Top-level serve helper
// ---------------------------------------------------------------------------

/**
 * Run the ANIP stdio server, reading newline-delimited JSON-RPC from
 * `input` and writing responses to `output`.
 */
export async function serveStdio(
  service: ANIPService,
  input: NodeJS.ReadableStream = process.stdin,
  output: NodeJS.WritableStream = process.stdout,
): Promise<void> {
  const server = new AnipStdioServer(service);
  await service.start();

  const rl = createInterface({ input, crlfDelay: Infinity });

  const writeLine = (msg: JsonRpcMessage): void => {
    output.write(JSON.stringify(msg) + "\n");
  };

  try {
    for await (const line of rl) {
      const trimmed = line.trim();
      if (trimmed === "") continue;

      let msg: Record<string, unknown>;
      try {
        msg = JSON.parse(trimmed);
      } catch {
        writeLine(makeError(null, PARSE_ERROR, "Parse error"));
        continue;
      }

      const response = await server.handleRequest(msg);

      if (Array.isArray(response)) {
        for (const item of response) {
          writeLine(item);
        }
      } else {
        writeLine(response);
      }
    }
  } finally {
    await service.shutdown();
    service.stop();
  }
}
