// Package stdioapi provides an ANIP stdio transport — a JSON-RPC 2.0 server
// that reads from stdin and writes to stdout, exposing all 9 ANIP protocol operations.
package stdioapi

import (
	"bufio"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/server"
	"github.com/anip-protocol/anip/packages/go/service"
)

// --- JSON-RPC 2.0 error codes ---

const (
	codeParseError     = -32700
	codeInvalidRequest = -32600
	codeMethodNotFound = -32601
	codeAuthError      = -32001
	codeScopeError     = -32002
	codeNotFound       = -32004
	codeInternalError  = -32603
)

// failureTypeToCode maps ANIP failure types to JSON-RPC error codes.
var failureTypeToCode = map[string]int{
	"authentication_required": codeAuthError,
	"invalid_token":           codeAuthError,
	"token_expired":           codeAuthError,
	"scope_insufficient":      codeScopeError,
	"budget_exceeded":         codeScopeError,
	"purpose_mismatch":        codeScopeError,
	"unknown_capability":      codeNotFound,
	"not_found":               codeNotFound,
	"internal_error":          codeInternalError,
	"unavailable":             codeInternalError,
	"concurrent_lock":         codeInternalError,
}

// validMethods is the set of supported ANIP JSON-RPC methods.
var validMethods = map[string]bool{
	"anip.discovery":       true,
	"anip.manifest":        true,
	"anip.jwks":            true,
	"anip.tokens.issue":    true,
	"anip.permissions":     true,
	"anip.invoke":          true,
	"anip.audit.query":     true,
	"anip.checkpoints.list": true,
	"anip.checkpoints.get":  true,
}

// --- JSON-RPC types ---

// request is a JSON-RPC 2.0 request object.
type request struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Method  string          `json:"method"`
	Params  json.RawMessage `json:"params,omitempty"`
}

// response is a JSON-RPC 2.0 response object.
type response struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      json.RawMessage `json:"id"`
	Result  any             `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

// rpcError is a JSON-RPC 2.0 error object.
type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Data    any    `json:"data,omitempty"`
}

// notification is a JSON-RPC 2.0 notification (no id).
type notification struct {
	JSONRPC string `json:"jsonrpc"`
	Method  string `json:"method"`
	Params  any    `json:"params"`
}

// --- Message constructors ---

func makeResponse(id json.RawMessage, result any) response {
	return response{JSONRPC: "2.0", ID: id, Result: result}
}

func makeError(id json.RawMessage, code int, message string, data any) response {
	e := &rpcError{Code: code, Message: message}
	if data != nil {
		e.Data = data
	}
	return response{JSONRPC: "2.0", ID: id, Error: e}
}

func makeNotification(method string, params any) notification {
	return notification{JSONRPC: "2.0", Method: method, Params: params}
}

// --- Server ---

// Server wraps an ANIP Service for the stdio JSON-RPC transport.
type Server struct {
	svc *service.Service
}

// NewServer creates a new stdio server wrapping the given service.
func NewServer(svc *service.Service) *Server {
	return &Server{svc: svc}
}

// ServeStdio starts the service, reads JSON-RPC requests from stdin,
// dispatches them, writes responses to stdout, and shuts down on EOF.
func ServeStdio(svc *service.Service) error {
	if err := svc.Start(); err != nil {
		return fmt.Errorf("start service: %w", err)
	}
	defer svc.Shutdown()

	srv := NewServer(svc)
	return srv.Serve(os.Stdin, os.Stdout)
}

// Serve reads newline-delimited JSON-RPC from r and writes responses to w.
// It returns nil on EOF.
func (s *Server) Serve(r io.Reader, w io.Writer) error {
	scanner := bufio.NewScanner(r)
	// Allow large messages (up to 10 MB).
	scanner.Buffer(make([]byte, 64*1024), 10*1024*1024)

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		messages := s.handleLine(line)
		for _, msg := range messages {
			data, err := json.Marshal(msg)
			if err != nil {
				continue
			}
			data = append(data, '\n')
			if _, err := w.Write(data); err != nil {
				return fmt.Errorf("write response: %w", err)
			}
		}
	}

	return scanner.Err()
}

// handleLine parses a single JSON-RPC request line and returns response message(s).
func (s *Server) handleLine(line []byte) []any {
	var req request
	if err := json.Unmarshal(line, &req); err != nil {
		return []any{makeError(nil, codeParseError, fmt.Sprintf("Parse error: %s", err), nil)}
	}

	resp := s.HandleRequest(req)
	return resp
}

// HandleRequest validates and dispatches a JSON-RPC request.
// Returns a slice of response/notification messages.
func (s *Server) HandleRequest(req request) []any {
	// Validate JSON-RPC 2.0 structure.
	if errMsg := validateRequest(req); errMsg != "" {
		return []any{makeError(req.ID, codeInvalidRequest, errMsg, nil)}
	}

	method := req.Method
	if !validMethods[method] {
		return []any{makeError(req.ID, codeMethodNotFound, fmt.Sprintf("Unknown method: %s", method), nil)}
	}

	// Parse params as map.
	var params map[string]any
	if len(req.Params) > 0 {
		if err := json.Unmarshal(req.Params, &params); err != nil {
			return []any{makeError(req.ID, codeInvalidRequest, "params must be a JSON object", nil)}
		}
	}
	if params == nil {
		params = map[string]any{}
	}

	// Dispatch.
	handler, ok := dispatchTable[method]
	if !ok {
		return []any{makeError(req.ID, codeInternalError, fmt.Sprintf("No handler for %s", method), nil)}
	}

	result, err := handler(s, params)
	if err != nil {
		var anipErr *core.ANIPError
		if errors.As(err, &anipErr) {
			code := codeInternalError
			if c, ok := failureTypeToCode[anipErr.ErrorType]; ok {
				code = c
			}
			return []any{makeError(req.ID, code, anipErr.Detail, map[string]any{
				"type":   anipErr.ErrorType,
				"detail": anipErr.Detail,
				"retry":  anipErr.Retry,
			})}
		}
		return []any{makeError(req.ID, codeInternalError, err.Error(), nil)}
	}

	// Streaming invoke returns (notifications, result) as streamingResult.
	if sr, ok := result.(*streamingResult); ok {
		var messages []any
		for _, n := range sr.notifications {
			messages = append(messages, n)
		}
		messages = append(messages, makeResponse(req.ID, sr.result))
		return messages
	}

	return []any{makeResponse(req.ID, result)}
}

// streamingResult holds progress notifications and the final result for streaming invocations.
type streamingResult struct {
	notifications []notification
	result        any
}

// --- Request validation ---

func validateRequest(req request) string {
	if req.JSONRPC != "2.0" {
		return "Missing or invalid 'jsonrpc' field (must be '2.0')"
	}
	if req.Method == "" {
		return "Missing 'method' field"
	}
	if req.ID == nil {
		return "Missing 'id' field (notifications not supported as requests)"
	}
	return ""
}

// --- Auth extraction ---

func extractAuth(params map[string]any) string {
	auth, ok := params["auth"]
	if !ok {
		return ""
	}
	authMap, ok := auth.(map[string]any)
	if !ok {
		return ""
	}
	bearer, _ := authMap["bearer"].(string)
	return bearer
}

// resolveJWT extracts and verifies a JWT bearer token from params.
func (s *Server) resolveJWT(params map[string]any) (*core.DelegationToken, error) {
	bearer := extractAuth(params)
	if bearer == "" {
		return nil, core.NewANIPError(core.FailureAuthRequired, "This method requires auth.bearer")
	}
	return s.svc.ResolveBearerToken(bearer)
}

// --- Method handlers ---

func handleDiscovery(s *Server, params map[string]any) (any, error) {
	return s.svc.GetDiscovery(""), nil
}

func handleManifest(s *Server, params map[string]any) (any, error) {
	bodyBytes, signature := s.svc.GetSignedManifest()
	var manifest any
	json.Unmarshal(bodyBytes, &manifest)
	return map[string]any{
		"manifest":  manifest,
		"signature": signature,
	}, nil
}

func handleJWKS(s *Server, params map[string]any) (any, error) {
	return s.svc.GetJWKS(), nil
}

func handleTokensIssue(s *Server, params map[string]any) (any, error) {
	bearer := extractAuth(params)
	if bearer == "" {
		return nil, core.NewANIPError(core.FailureAuthRequired, "This method requires auth.bearer")
	}

	// Try bootstrap auth (API key) first, then ANIP JWT.
	principal, ok := s.svc.AuthenticateBearer(bearer)
	if !ok {
		// Try resolving as JWT.
		token, err := s.svc.ResolveBearerToken(bearer)
		if err != nil {
			return nil, core.NewANIPError(core.FailureInvalidToken, "Bearer token not recognized")
		}
		principal = token.Subject
	}

	// Build token request from params.
	var req core.TokenRequest
	if v, ok := params["subject"].(string); ok {
		req.Subject = v
	}
	if v, ok := params["scope"].([]any); ok {
		for _, s := range v {
			if str, ok := s.(string); ok {
				req.Scope = append(req.Scope, str)
			}
		}
	}
	if v, ok := params["capability"].(string); ok {
		req.Capability = v
	}
	if v, ok := params["parent_token"].(string); ok {
		req.ParentToken = v
	}
	if v, ok := params["purpose_parameters"].(map[string]any); ok {
		req.PurposeParameters = v
	}
	if v, ok := params["ttl_hours"].(float64); ok {
		req.TTLHours = int(v)
	}
	if v, ok := params["caller_class"].(string); ok {
		req.CallerClass = v
	}

	resp, err := s.svc.IssueToken(principal, req)
	if err != nil {
		return nil, err
	}

	// Convert to map for JSON-RPC response.
	data, _ := json.Marshal(resp)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result, nil
}

func handlePermissions(s *Server, params map[string]any) (any, error) {
	token, err := s.resolveJWT(params)
	if err != nil {
		return nil, err
	}

	perm := s.svc.DiscoverPermissions(token)

	// Convert struct to map for JSON-RPC response.
	data, _ := json.Marshal(perm)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result, nil
}

func handleInvoke(s *Server, params map[string]any) (any, error) {
	token, err := s.resolveJWT(params)
	if err != nil {
		return nil, err
	}

	capability, _ := params["capability"].(string)
	if capability == "" {
		return nil, core.NewANIPError(core.FailureUnknownCapability, "Missing 'capability' in params")
	}

	parameters, _ := params["parameters"].(map[string]any)
	if parameters == nil {
		parameters = map[string]any{}
	}

	clientRefID, _ := params["client_reference_id"].(string)
	stream, _ := params["stream"].(bool)

	if stream {
		// Streaming invocation — collect progress notifications then return final result.
		sr, err := s.svc.InvokeStream(capability, token, parameters, service.InvokeOpts{
			ClientReferenceID: clientRefID,
			Stream:            true,
		})
		if err != nil {
			return nil, err
		}

		var notifications []notification
		var finalResult any

		for event := range sr.Events {
			switch event.Type {
			case "progress":
				notifications = append(notifications, makeNotification("anip.invoke.progress", event.Payload))
			case "completed", "failed":
				finalResult = event.Payload
			}
		}

		return &streamingResult{
			notifications: notifications,
			result:        finalResult,
		}, nil
	}

	// Unary invocation.
	result, err := s.svc.Invoke(capability, token, parameters, service.InvokeOpts{
		ClientReferenceID: clientRefID,
	})
	if err != nil {
		return nil, err
	}
	return result, nil
}

func handleAuditQuery(s *Server, params map[string]any) (any, error) {
	token, err := s.resolveJWT(params)
	if err != nil {
		return nil, err
	}

	var filters server.AuditFilters
	if v, ok := params["capability"].(string); ok {
		filters.Capability = v
	}
	if v, ok := params["since"].(string); ok {
		filters.Since = v
	}
	if v, ok := params["invocation_id"].(string); ok {
		filters.InvocationID = v
	}
	if v, ok := params["client_reference_id"].(string); ok {
		filters.ClientReferenceID = v
	}
	if v, ok := params["limit"].(float64); ok {
		filters.Limit = int(v)
	}

	resp, err := s.svc.QueryAudit(token, filters)
	if err != nil {
		return nil, err
	}

	// Convert struct to map for JSON-RPC response.
	data, _ := json.Marshal(resp)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result, nil
}

func handleCheckpointsList(s *Server, params map[string]any) (any, error) {
	limit := 10
	if v, ok := params["limit"].(float64); ok {
		limit = int(v)
	}

	resp, err := s.svc.ListCheckpoints(limit)
	if err != nil {
		return nil, err
	}

	// Convert struct to map for JSON-RPC response.
	data, _ := json.Marshal(resp)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result, nil
}

func handleCheckpointsGet(s *Server, params map[string]any) (any, error) {
	id, _ := params["id"].(string)
	if id == "" {
		return nil, core.NewANIPError(core.FailureNotFound, "Missing 'id' in params")
	}

	includeProof, _ := params["include_proof"].(bool)
	leafIndex := 0
	if v, ok := params["leaf_index"].(float64); ok {
		leafIndex = int(v)
	}

	consistencyFrom, _ := params["consistency_from"].(string)

	resp, err := s.svc.GetCheckpoint(id, includeProof, leafIndex, consistencyFrom)
	if err != nil {
		return nil, err
	}
	if resp == nil {
		return nil, core.NewANIPError(core.FailureNotFound, fmt.Sprintf("Checkpoint not found: %s", id))
	}

	// Convert struct to map for JSON-RPC response.
	data, _ := json.Marshal(resp)
	var result map[string]any
	json.Unmarshal(data, &result)
	return result, nil
}

// --- Dispatch table ---

type handlerFunc func(s *Server, params map[string]any) (any, error)

var dispatchTable = map[string]handlerFunc{
	"anip.discovery":        handleDiscovery,
	"anip.manifest":         handleManifest,
	"anip.jwks":             handleJWKS,
	"anip.tokens.issue":     handleTokensIssue,
	"anip.permissions":      handlePermissions,
	"anip.invoke":           handleInvoke,
	"anip.audit.query":      handleAuditQuery,
	"anip.checkpoints.list": handleCheckpointsList,
	"anip.checkpoints.get":  handleCheckpointsGet,
}
