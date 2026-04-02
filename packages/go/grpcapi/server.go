// Package grpcapi provides an ANIP gRPC transport — a gRPC server that
// exposes all 10 ANIP protocol operations, dispatching to the service layer.
package grpcapi

import (
	"context"
	"encoding/json"
	"fmt"
	"net"
	"strings"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/anip-protocol/anip/packages/go/core"
	pb "github.com/anip-protocol/anip/packages/go/grpcapi/proto/anip/v1"
	"github.com/anip-protocol/anip/packages/go/server"
	"github.com/anip-protocol/anip/packages/go/service"
)

// AnipGrpcServer implements the generated AnipServiceServer interface,
// dispatching each RPC to the underlying ANIP service.
type AnipGrpcServer struct {
	pb.UnimplementedAnipServiceServer
	service *service.Service
}

// NewAnipGrpcServer creates a new gRPC server wrapping the given service.
func NewAnipGrpcServer(svc *service.Service) *AnipGrpcServer {
	return &AnipGrpcServer{service: svc}
}

// --- Auth helpers ---

// extractBearer extracts a bearer token from gRPC call metadata.
// Looks for "authorization: Bearer <token>" in incoming metadata.
func extractBearer(ctx context.Context) string {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return ""
	}
	vals := md.Get("authorization")
	if len(vals) == 0 {
		return ""
	}
	if strings.HasPrefix(vals[0], "Bearer ") {
		return strings.TrimPrefix(vals[0], "Bearer ")
	}
	return ""
}

// resolveJWT extracts and verifies a JWT bearer token from gRPC metadata.
func (s *AnipGrpcServer) resolveJWT(ctx context.Context) (*core.DelegationToken, error) {
	bearer := extractBearer(ctx)
	if bearer == "" {
		return nil, status.Error(codes.Unauthenticated, "missing authorization metadata with Bearer token")
	}
	token, err := s.service.ResolveBearerToken(bearer)
	if err != nil {
		return nil, status.Error(codes.Unauthenticated, "invalid bearer token")
	}
	return token, nil
}

// toAnipFailure converts a core.ANIPError to the protobuf AnipFailure message.
func toAnipFailure(anipErr *core.ANIPError) *pb.AnipFailure {
	f := &pb.AnipFailure{
		Type:   anipErr.ErrorType,
		Detail: anipErr.Detail,
		Retry:  anipErr.Retry,
	}
	if anipErr.Resolution != nil {
		resJSON, err := json.Marshal(anipErr.Resolution)
		if err == nil {
			f.ResolutionJson = string(resJSON)
		}
	}
	return f
}

// mapToAnipFailure converts a map[string]any failure to protobuf AnipFailure.
func mapToAnipFailure(m map[string]any) *pb.AnipFailure {
	f := &pb.AnipFailure{}
	if v, ok := m["type"].(string); ok {
		f.Type = v
	}
	if v, ok := m["detail"].(string); ok {
		f.Detail = v
	}
	if v, ok := m["retry"].(bool); ok {
		f.Retry = v
	}
	if v, ok := m["resolution"]; ok && v != nil {
		resJSON, err := json.Marshal(v)
		if err == nil {
			f.ResolutionJson = string(resJSON)
		}
	}
	return f
}

// mapToBudgetContext converts a map[string]any budget_context to protobuf BudgetContext.
// Returns nil if the map is nil or empty.
func mapToBudgetContext(m map[string]any) *pb.BudgetContext {
	if m == nil {
		return nil
	}
	bc := &pb.BudgetContext{}
	if v, ok := m["budget_max"].(float64); ok {
		bc.BudgetMax = v
	}
	if v, ok := m["budget_currency"].(string); ok {
		bc.BudgetCurrency = v
	}
	if v, ok := m["cost_check_amount"].(float64); ok {
		bc.CostCheckAmount = v
	}
	if v, ok := m["cost_certainty"].(string); ok {
		bc.CostCertainty = v
	}
	if v, ok := m["cost_actual"].(float64); ok {
		bc.CostActual = v
	}
	if v, ok := m["within_budget"].(bool); ok {
		bc.WithinBudget = v
	}
	return bc
}

// --- RPC implementations ---

// Discovery returns the full discovery document as a JSON string.
func (s *AnipGrpcServer) Discovery(ctx context.Context, req *pb.DiscoveryRequest) (*pb.DiscoveryResponse, error) {
	doc := s.service.GetDiscovery("")
	jsonBytes, err := json.Marshal(doc)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal discovery: %v", err)
	}
	return &pb.DiscoveryResponse{Json: string(jsonBytes)}, nil
}

// Manifest returns the signed manifest.
func (s *AnipGrpcServer) Manifest(ctx context.Context, req *pb.ManifestRequest) (*pb.ManifestResponse, error) {
	bodyBytes, signature := s.service.GetSignedManifest()
	return &pb.ManifestResponse{
		ManifestJson: string(bodyBytes),
		Signature:    signature,
	}, nil
}

// Jwks returns the JWKS document as a JSON string.
func (s *AnipGrpcServer) Jwks(ctx context.Context, req *pb.JwksRequest) (*pb.JwksResponse, error) {
	jwks := s.service.GetJWKS()
	jsonBytes, err := json.Marshal(jwks)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal jwks: %v", err)
	}
	return &pb.JwksResponse{Json: string(jsonBytes)}, nil
}

// IssueToken issues a delegation token. Accepts bootstrap (API key) or JWT auth.
func (s *AnipGrpcServer) IssueToken(ctx context.Context, req *pb.IssueTokenRequest) (*pb.IssueTokenResponse, error) {
	bearer := extractBearer(ctx)
	if bearer == "" {
		return nil, status.Error(codes.Unauthenticated, "missing authorization metadata with Bearer token")
	}

	// Try bootstrap auth (API key) first, then ANIP JWT.
	principal, ok := s.service.AuthenticateBearer(bearer)
	if !ok {
		// Try resolving as JWT.
		token, err := s.service.ResolveBearerToken(bearer)
		if err != nil {
			return nil, status.Error(codes.Unauthenticated, "bearer token not recognized")
		}
		principal = token.Subject
	}

	// Build token request.
	tokenReq := core.TokenRequest{
		Subject:     req.Subject,
		Scope:       req.Scope,
		Capability:  req.Capability,
		TTLHours:    int(req.TtlHours),
		CallerClass: req.CallerClass,
	}
	if req.ParentToken != "" {
		tokenReq.ParentToken = req.ParentToken
	}
	if req.PurposeParametersJson != "" {
		var pp map[string]any
		if err := json.Unmarshal([]byte(req.PurposeParametersJson), &pp); err == nil {
			tokenReq.PurposeParameters = pp
		}
	}
	// Read budget from the protobuf Budget field.
	if req.Budget != nil && req.Budget.Currency != "" && req.Budget.MaxAmount > 0 {
		tokenReq.Budget = &core.Budget{
			Currency:  req.Budget.Currency,
			MaxAmount: req.Budget.MaxAmount,
		}
	}

	resp, err := s.service.IssueToken(principal, tokenReq)
	if err != nil {
		var anipErr *core.ANIPError
		if ok := isANIPError(err, &anipErr); ok {
			return &pb.IssueTokenResponse{
				Issued:  false,
				Failure: toAnipFailure(anipErr),
			}, nil
		}
		return nil, status.Errorf(codes.Internal, "issue token: %v", err)
	}

	pbResp := &pb.IssueTokenResponse{
		Issued:  resp.Issued,
		TokenId: resp.TokenID,
		Token:   resp.Token,
		Expires: resp.Expires,
	}
	if resp.Budget != nil {
		pbResp.Budget = &pb.Budget{
			Currency:  resp.Budget.Currency,
			MaxAmount: resp.Budget.MaxAmount,
		}
	}
	return pbResp, nil
}

// Permissions returns the permissions for the authenticated token.
func (s *AnipGrpcServer) Permissions(ctx context.Context, req *pb.PermissionsRequest) (*pb.PermissionsResponse, error) {
	token, err := s.resolveJWT(ctx)
	if err != nil {
		return nil, err // already a gRPC status error
	}

	perm := s.service.DiscoverPermissions(token)
	jsonBytes, err := json.Marshal(perm)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal permissions: %v", err)
	}

	return &pb.PermissionsResponse{
		Success: true,
		Json:    string(jsonBytes),
	}, nil
}

// Invoke performs a unary capability invocation.
func (s *AnipGrpcServer) Invoke(ctx context.Context, req *pb.InvokeRequest) (*pb.InvokeResponse, error) {
	token, err := s.resolveJWT(ctx)
	if err != nil {
		return nil, err // already a gRPC status error
	}

	capability := req.Capability
	var params map[string]any
	if req.ParametersJson != "" {
		if err := json.Unmarshal([]byte(req.ParametersJson), &params); err != nil {
			return nil, status.Errorf(codes.InvalidArgument, "invalid parameters_json: %v", err)
		}
	}
	if params == nil {
		params = map[string]any{}
	}

	// Extract budget from params (gRPC clients include it in parameters_json).
	var budget *core.Budget
	if budgetRaw, ok := params["budget"].(map[string]any); ok {
		currency, _ := budgetRaw["currency"].(string)
		maxAmount, _ := budgetRaw["max_amount"].(float64)
		if currency != "" && maxAmount > 0 {
			budget = &core.Budget{Currency: currency, MaxAmount: maxAmount}
		}
		delete(params, "budget") // Don't pass budget as a parameter.
	}

	result, err := s.service.Invoke(capability, token, params, service.InvokeOpts{
		ClientReferenceID:  req.ClientReferenceId,
		TaskID:             req.TaskId,
		ParentInvocationID: req.ParentInvocationId,
		UpstreamService:    req.UpstreamService,
		Budget:             budget,
	})
	if err != nil {
		var anipErr *core.ANIPError
		if ok := isANIPError(err, &anipErr); ok {
			return &pb.InvokeResponse{
				Success:             false,
				ClientReferenceId:   req.ClientReferenceId,
				Failure:             toAnipFailure(anipErr),
				TaskId:              req.TaskId,
				ParentInvocationId:  req.ParentInvocationId,
				UpstreamService:     req.UpstreamService,
			}, nil
		}
		return nil, status.Errorf(codes.Internal, "invoke: %v", err)
	}

	// The service.Invoke returns a map with success/failure fields.
	resp := &pb.InvokeResponse{
		ClientReferenceId: req.ClientReferenceId,
	}

	if success, ok := result["success"].(bool); ok {
		resp.Success = success
	}
	if invID, ok := result["invocation_id"].(string); ok {
		resp.InvocationId = invID
	}
	if cri, ok := result["client_reference_id"].(string); ok {
		resp.ClientReferenceId = cri
	}
	if tid, ok := result["task_id"].(string); ok {
		resp.TaskId = tid
	}
	if pid, ok := result["parent_invocation_id"].(string); ok {
		resp.ParentInvocationId = pid
	}
	if us, ok := result["upstream_service"].(string); ok {
		resp.UpstreamService = us
	}

	if resp.Success {
		if r, ok := result["result"]; ok {
			rJSON, err := json.Marshal(r)
			if err == nil {
				resp.ResultJson = string(rJSON)
			}
		}
		if ca, ok := result["cost_actual"]; ok && ca != nil {
			caJSON, err := json.Marshal(ca)
			if err == nil {
				resp.CostActualJson = string(caJSON)
			}
		}
	} else {
		if f, ok := result["failure"].(map[string]any); ok {
			resp.Failure = mapToAnipFailure(f)
		}
	}

	// Populate budget_context if present (both success and failure).
	if bc, ok := result["budget_context"].(map[string]any); ok {
		resp.BudgetContext = mapToBudgetContext(bc)
	}

	return resp, nil
}

// InvokeStream performs a streaming capability invocation.
func (s *AnipGrpcServer) InvokeStream(req *pb.InvokeRequest, stream grpc.ServerStreamingServer[pb.InvokeEvent]) error {
	ctx := stream.Context()
	token, err := s.resolveJWT(ctx)
	if err != nil {
		return err // already a gRPC status error
	}

	capability := req.Capability
	var params map[string]any
	if req.ParametersJson != "" {
		if err := json.Unmarshal([]byte(req.ParametersJson), &params); err != nil {
			return status.Errorf(codes.InvalidArgument, "invalid parameters_json: %v", err)
		}
	}
	if params == nil {
		params = map[string]any{}
	}

	sr, err := s.service.InvokeStream(capability, token, params, service.InvokeOpts{
		ClientReferenceID:  req.ClientReferenceId,
		TaskID:             req.TaskId,
		ParentInvocationID: req.ParentInvocationId,
		UpstreamService:    req.UpstreamService,
		Stream:             true,
	})
	if err != nil {
		var anipErr *core.ANIPError
		if ok := isANIPError(err, &anipErr); ok {
			// Send a single failed event and close.
			failedEvent := &pb.InvokeEvent{
				Event: &pb.InvokeEvent_Failed{
					Failed: &pb.FailedEvent{
						ClientReferenceId: req.ClientReferenceId,
						Failure:           toAnipFailure(anipErr),
					},
				},
			}
			_ = stream.Send(failedEvent)
			return nil
		}
		return status.Errorf(codes.Internal, "invoke stream: %v", err)
	}

	for event := range sr.Events {
		select {
		case <-ctx.Done():
			sr.Cancel()
			return ctx.Err()
		default:
		}

		switch event.Type {
		case "progress":
			payloadJSON, _ := json.Marshal(event.Payload)
			invID, _ := event.Payload["invocation_id"].(string)
			grpcEvent := &pb.InvokeEvent{
				Event: &pb.InvokeEvent_Progress{
					Progress: &pb.ProgressEvent{
						InvocationId: invID,
						PayloadJson:  string(payloadJSON),
					},
				},
			}
			if err := stream.Send(grpcEvent); err != nil {
				sr.Cancel()
				return err
			}

		case "completed":
			invID, _ := event.Payload["invocation_id"].(string)
			criVal, _ := event.Payload["client_reference_id"].(string)
			tidVal, _ := event.Payload["task_id"].(string)
			pidVal, _ := event.Payload["parent_invocation_id"].(string)
			usVal, _ := event.Payload["upstream_service"].(string)
			var resultJSON string
			if r, ok := event.Payload["result"]; ok && r != nil {
				rBytes, _ := json.Marshal(r)
				resultJSON = string(rBytes)
			}
			var costJSON string
			if ca, ok := event.Payload["cost_actual"]; ok && ca != nil {
				caBytes, _ := json.Marshal(ca)
				costJSON = string(caBytes)
			}
			completed := &pb.CompletedEvent{
				InvocationId:       invID,
				ClientReferenceId:  criVal,
				TaskId:             tidVal,
				ParentInvocationId: pidVal,
				UpstreamService:    usVal,
				ResultJson:         resultJSON,
				CostActualJson:     costJSON,
			}
			if bc, ok := event.Payload["budget_context"].(map[string]any); ok {
				completed.BudgetContext = mapToBudgetContext(bc)
			}
			grpcEvent := &pb.InvokeEvent{
				Event: &pb.InvokeEvent_Completed{
					Completed: completed,
				},
			}
			if err := stream.Send(grpcEvent); err != nil {
				sr.Cancel()
				return err
			}

		case "failed":
			invID, _ := event.Payload["invocation_id"].(string)
			criVal, _ := event.Payload["client_reference_id"].(string)
			tidVal, _ := event.Payload["task_id"].(string)
			pidVal, _ := event.Payload["parent_invocation_id"].(string)
			usVal, _ := event.Payload["upstream_service"].(string)
			var failure *pb.AnipFailure
			if f, ok := event.Payload["failure"].(map[string]any); ok {
				failure = mapToAnipFailure(f)
			}
			failed := &pb.FailedEvent{
				InvocationId:       invID,
				ClientReferenceId:  criVal,
				TaskId:             tidVal,
				ParentInvocationId: pidVal,
				UpstreamService:    usVal,
				Failure:            failure,
			}
			if bc, ok := event.Payload["budget_context"].(map[string]any); ok {
				failed.BudgetContext = mapToBudgetContext(bc)
			}
			grpcEvent := &pb.InvokeEvent{
				Event: &pb.InvokeEvent_Failed{
					Failed: failed,
				},
			}
			if err := stream.Send(grpcEvent); err != nil {
				sr.Cancel()
				return err
			}
		}
	}

	return nil
}

// QueryAudit queries audit entries scoped to the authenticated token.
func (s *AnipGrpcServer) QueryAudit(ctx context.Context, req *pb.QueryAuditRequest) (*pb.QueryAuditResponse, error) {
	token, err := s.resolveJWT(ctx)
	if err != nil {
		return nil, err // already a gRPC status error
	}

	filters := server.AuditFilters{
		Capability:         req.Capability,
		Since:              req.Since,
		InvocationID:       req.InvocationId,
		ClientReferenceID:  req.ClientReferenceId,
		TaskID:             req.TaskId,
		ParentInvocationID: req.ParentInvocationId,
		EventClass:         req.EventClass,
		Limit:              int(req.Limit),
	}

	resp, err := s.service.QueryAudit(token, filters)
	if err != nil {
		var anipErr *core.ANIPError
		if ok := isANIPError(err, &anipErr); ok {
			return &pb.QueryAuditResponse{
				Success: false,
				Failure: toAnipFailure(anipErr),
			}, nil
		}
		return nil, status.Errorf(codes.Internal, "query audit: %v", err)
	}

	jsonBytes, err := json.Marshal(resp)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal audit: %v", err)
	}

	return &pb.QueryAuditResponse{
		Success: true,
		Json:    string(jsonBytes),
	}, nil
}

// ListCheckpoints returns a list of checkpoints.
func (s *AnipGrpcServer) ListCheckpoints(ctx context.Context, req *pb.ListCheckpointsRequest) (*pb.ListCheckpointsResponse, error) {
	resp, err := s.service.ListCheckpoints(int(req.Limit))
	if err != nil {
		return nil, status.Errorf(codes.Internal, "list checkpoints: %v", err)
	}

	jsonBytes, err := json.Marshal(resp)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal checkpoints: %v", err)
	}

	return &pb.ListCheckpointsResponse{Json: string(jsonBytes)}, nil
}

// GetCheckpoint returns a single checkpoint with optional inclusion proof and/or consistency proof.
func (s *AnipGrpcServer) GetCheckpoint(ctx context.Context, req *pb.GetCheckpointRequest) (*pb.GetCheckpointResponse, error) {
	resp, err := s.service.GetCheckpoint(req.Id, req.IncludeProof, int(req.LeafIndex), req.ConsistencyFrom)
	if err != nil {
		var anipErr *core.ANIPError
		if ok := isANIPError(err, &anipErr); ok {
			if anipErr.ErrorType == core.FailureNotFound {
				return nil, status.Errorf(codes.NotFound, "%s", anipErr.Detail)
			}
			return nil, status.Errorf(codes.Internal, "%s", anipErr.Detail)
		}
		return nil, status.Errorf(codes.Internal, "get checkpoint: %v", err)
	}

	jsonBytes, err := json.Marshal(resp)
	if err != nil {
		return nil, status.Errorf(codes.Internal, "marshal checkpoint: %v", err)
	}

	return &pb.GetCheckpointResponse{Json: string(jsonBytes)}, nil
}

// --- Helper ---

// isANIPError checks if an error is an *core.ANIPError and extracts it.
func isANIPError(err error, target **core.ANIPError) bool {
	if anipErr, ok := err.(*core.ANIPError); ok {
		*target = anipErr
		return true
	}
	return false
}

// --- Server lifecycle ---

// ServeGrpc starts a gRPC server on the given port, serving the ANIP protocol.
// It starts the service, registers the gRPC server, and blocks until the server stops.
func ServeGrpc(svc *service.Service, port int) error {
	lis, err := net.Listen("tcp", fmt.Sprintf(":%d", port))
	if err != nil {
		return fmt.Errorf("listen: %w", err)
	}
	return ServeGrpcOnListener(svc, lis)
}

// ServeGrpcOnListener starts a gRPC server on the given listener.
// Useful for testing with a random port.
func ServeGrpcOnListener(svc *service.Service, lis net.Listener) error {
	s := grpc.NewServer()
	pb.RegisterAnipServiceServer(s, NewAnipGrpcServer(svc))
	if err := svc.Start(); err != nil {
		return fmt.Errorf("start service: %w", err)
	}
	defer svc.Shutdown()
	return s.Serve(lis)
}
