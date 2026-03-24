package grpcapi

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"strings"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	"github.com/anip-protocol/anip/packages/go/core"
	pb "github.com/anip-protocol/anip/packages/go/grpcapi/proto/anip/v1"
	"github.com/anip-protocol/anip/packages/go/service"
)

// --- Test helpers ---

// testEnv holds a running gRPC server and client for tests.
type testEnv struct {
	svc    *service.Service
	client pb.AnipServiceClient
	conn   *grpc.ClientConn
	stop   func()
}

// newTestEnv creates a service with an echo capability, starts a gRPC server
// on a random port, and returns a connected client.
func newTestEnv(t *testing.T) *testEnv {
	t.Helper()

	svc := service.New(service.Config{
		ServiceID: "test-grpc-service",
		Capabilities: []service.CapabilityDef{
			{
				Declaration: core.CapabilityDeclaration{
					Name:            "echo",
					Description:     "Echoes input back",
					ContractVersion: "1.0",
					Inputs: []core.CapabilityInput{
						{Name: "message", Type: "string", Required: false},
					},
					Output: core.CapabilityOutput{
						Type:   "object",
						Fields: []string{"echo"},
					},
					SideEffect: core.SideEffect{
						Type:           "read",
						RollbackWindow: "not_applicable",
					},
					MinimumScope:  []string{"echo"},
					ResponseModes: []string{"unary", "streaming"},
				},
				Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
					msg, _ := params["message"].(string)
					if msg == "" {
						msg = "hello"
					}
					// Emit progress if streaming.
					if ctx.EmitProgress != nil {
						_ = ctx.EmitProgress(map[string]any{"step": "processing"})
					}
					return map[string]any{"echo": msg}, nil
				},
			},
		},
		Storage: ":memory:",
		Trust:   "signed",
		Authenticate: func(bearer string) (string, bool) {
			if bearer == "test-api-key" {
				return "human:tester@example.com", true
			}
			return "", false
		},
		RetentionIntervalSeconds: -1, // disable background retention
	})

	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}

	// Listen on random port.
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatalf("Listen error: %v", err)
	}

	s := grpc.NewServer()
	pb.RegisterAnipServiceServer(s, NewAnipGrpcServer(svc))

	go func() {
		if err := s.Serve(lis); err != nil {
			// Server stopped — expected on cleanup.
		}
	}()

	// Connect client.
	conn, err := grpc.NewClient(
		lis.Addr().String(),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		s.GracefulStop()
		svc.Shutdown()
		t.Fatalf("Dial error: %v", err)
	}

	client := pb.NewAnipServiceClient(conn)

	return &testEnv{
		svc:    svc,
		client: client,
		conn:   conn,
		stop: func() {
			conn.Close()
			s.GracefulStop()
			svc.Shutdown()
		},
	}
}

// issueTestToken issues a token via API key auth and returns the JWT string.
func issueTestToken(t *testing.T, svc *service.Service) string {
	t.Helper()
	resp, err := svc.IssueToken("human:tester@example.com", core.TokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected token to be issued")
	}
	return resp.Token
}

// withBearer adds an "authorization: Bearer <token>" metadata to the context.
func withBearer(ctx context.Context, token string) context.Context {
	return metadata.AppendToOutgoingContext(ctx, "authorization", "Bearer "+token)
}

// --- Tests ---

func TestDiscovery(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	resp, err := env.client.Discovery(context.Background(), &pb.DiscoveryRequest{})
	if err != nil {
		t.Fatalf("Discovery() error: %v", err)
	}
	if resp.Json == "" {
		t.Fatal("expected non-empty JSON in discovery response")
	}

	var doc map[string]any
	if err := json.Unmarshal([]byte(resp.Json), &doc); err != nil {
		t.Fatalf("unmarshal discovery JSON: %v", err)
	}
	disc, ok := doc["anip_discovery"].(map[string]any)
	if !ok {
		t.Fatal("expected anip_discovery object in response")
	}
	if disc["protocol"] != core.ProtocolVersion {
		t.Fatalf("expected protocol %q, got %v", core.ProtocolVersion, disc["protocol"])
	}
	caps, ok := disc["capabilities"].(map[string]any)
	if !ok {
		t.Fatal("expected capabilities map")
	}
	if _, ok := caps["echo"]; !ok {
		t.Fatal("expected echo capability in discovery")
	}
}

func TestManifest(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	resp, err := env.client.Manifest(context.Background(), &pb.ManifestRequest{})
	if err != nil {
		t.Fatalf("Manifest() error: %v", err)
	}
	if resp.ManifestJson == "" {
		t.Fatal("expected non-empty manifest JSON")
	}
	if resp.Signature == "" {
		t.Fatal("expected non-empty signature")
	}

	var manifest map[string]any
	if err := json.Unmarshal([]byte(resp.ManifestJson), &manifest); err != nil {
		t.Fatalf("unmarshal manifest JSON: %v", err)
	}
	if manifest["protocol"] == nil {
		t.Fatal("expected protocol field in manifest")
	}
}

func TestJwks(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	resp, err := env.client.Jwks(context.Background(), &pb.JwksRequest{})
	if err != nil {
		t.Fatalf("Jwks() error: %v", err)
	}
	if resp.Json == "" {
		t.Fatal("expected non-empty JWKS JSON")
	}

	var jwks map[string]any
	if err := json.Unmarshal([]byte(resp.Json), &jwks); err != nil {
		t.Fatalf("unmarshal JWKS JSON: %v", err)
	}
	if jwks["keys"] == nil {
		t.Fatal("expected keys in JWKS response")
	}
}

func TestIssueTokenWithAPIKey(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	ctx := withBearer(context.Background(), "test-api-key")
	resp, err := env.client.IssueToken(ctx, &pb.IssueTokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true")
	}
	if resp.Token == "" {
		t.Fatal("expected non-empty token")
	}
	if resp.TokenId == "" {
		t.Fatal("expected non-empty token_id")
	}
}

func TestIssueTokenWithJWT(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	ctx := withBearer(context.Background(), jwt)
	resp, err := env.client.IssueToken(ctx, &pb.IssueTokenRequest{
		Subject:    "agent:sub-agent",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err != nil {
		t.Fatalf("IssueToken() error: %v", err)
	}
	if !resp.Issued {
		t.Fatal("expected issued=true for JWT-based token issuance")
	}
}

func TestIssueTokenNoAuth(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	_, err := env.client.IssueToken(context.Background(), &pb.IssueTokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err == nil {
		t.Fatal("expected error for missing auth")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestIssueTokenBadKey(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	ctx := withBearer(context.Background(), "invalid-key")
	_, err := env.client.IssueToken(ctx, &pb.IssueTokenRequest{
		Subject:    "human:tester@example.com",
		Scope:      []string{"echo"},
		Capability: "echo",
	})
	if err == nil {
		t.Fatal("expected error for bad key")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestPermissions(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	ctx := withBearer(context.Background(), jwt)
	resp, err := env.client.Permissions(ctx, &pb.PermissionsRequest{})
	if err != nil {
		t.Fatalf("Permissions() error: %v", err)
	}
	if !resp.Success {
		t.Fatal("expected success=true")
	}
	if resp.Json == "" {
		t.Fatal("expected non-empty permissions JSON")
	}

	var perm map[string]any
	if err := json.Unmarshal([]byte(resp.Json), &perm); err != nil {
		t.Fatalf("unmarshal permissions: %v", err)
	}
	if perm["available"] == nil {
		t.Fatal("expected available in permissions")
	}
}

func TestPermissionsNoAuth(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	_, err := env.client.Permissions(context.Background(), &pb.PermissionsRequest{})
	if err == nil {
		t.Fatal("expected error for missing auth")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestInvoke(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	paramsJSON, _ := json.Marshal(map[string]any{"message": "world"})
	ctx := withBearer(context.Background(), jwt)
	resp, err := env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: string(paramsJSON),
	})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}
	if !resp.Success {
		t.Fatalf("expected success=true, got false (failure: %v)", resp.Failure)
	}
	if resp.InvocationId == "" {
		t.Fatal("expected non-empty invocation_id")
	}

	var result map[string]any
	if err := json.Unmarshal([]byte(resp.ResultJson), &result); err != nil {
		t.Fatalf("unmarshal result: %v", err)
	}
	if result["echo"] != "world" {
		t.Fatalf("expected echo='world', got %v", result["echo"])
	}
}

func TestInvokeNoAuth(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	paramsJSON, _ := json.Marshal(map[string]any{"message": "test"})
	_, err := env.client.Invoke(context.Background(), &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: string(paramsJSON),
	})
	if err == nil {
		t.Fatal("expected error for missing auth")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestInvokeUnknownCapability(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	ctx := withBearer(context.Background(), jwt)
	resp, err := env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "nonexistent",
		ParametersJson: "{}",
	})
	if err != nil {
		t.Fatalf("Invoke() error: %v (expected application-level failure, not gRPC error)", err)
	}
	if resp.Success {
		t.Fatal("expected success=false for unknown capability")
	}
	if resp.Failure == nil {
		t.Fatal("expected failure to be set")
	}
	if resp.Failure.Type != "unknown_capability" {
		t.Fatalf("expected failure type 'unknown_capability', got %q", resp.Failure.Type)
	}
}

func TestInvokeStream(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	paramsJSON, _ := json.Marshal(map[string]any{"message": "stream-test"})
	ctx := withBearer(context.Background(), jwt)
	stream, err := env.client.InvokeStream(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: string(paramsJSON),
	})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}

	var progressCount int
	var completed *pb.CompletedEvent

	for {
		event, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("Recv() error: %v", err)
		}

		switch e := event.Event.(type) {
		case *pb.InvokeEvent_Progress:
			progressCount++
			if e.Progress.InvocationId == "" {
				t.Fatal("expected non-empty invocation_id in progress event")
			}
		case *pb.InvokeEvent_Completed:
			completed = e.Completed
		case *pb.InvokeEvent_Failed:
			t.Fatalf("unexpected failed event: %v", e.Failed.Failure)
		}
	}

	if progressCount == 0 {
		t.Fatal("expected at least one progress event")
	}
	if completed == nil {
		t.Fatal("expected a completed event")
	}
	if completed.InvocationId == "" {
		t.Fatal("expected non-empty invocation_id in completed event")
	}

	var result map[string]any
	if err := json.Unmarshal([]byte(completed.ResultJson), &result); err != nil {
		t.Fatalf("unmarshal completed result: %v", err)
	}
	if result["echo"] != "stream-test" {
		t.Fatalf("expected echo='stream-test', got %v", result["echo"])
	}
}

func TestInvokeStreamNoAuth(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	stream, err := env.client.InvokeStream(context.Background(), &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: "{}",
	})
	if err != nil {
		t.Fatalf("InvokeStream() initial error: %v", err)
	}
	// The auth error may come on the first Recv.
	_, err = stream.Recv()
	if err == nil {
		t.Fatal("expected error for missing auth")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestQueryAudit(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	jwt := issueTestToken(t, env.svc)

	// Invoke to create an audit entry first.
	paramsJSON, _ := json.Marshal(map[string]any{"message": "audit-test"})
	ctx := withBearer(context.Background(), jwt)
	_, err := env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: string(paramsJSON),
	})
	if err != nil {
		t.Fatalf("Invoke() error: %v", err)
	}

	resp, err := env.client.QueryAudit(ctx, &pb.QueryAuditRequest{})
	if err != nil {
		t.Fatalf("QueryAudit() error: %v", err)
	}
	if !resp.Success {
		t.Fatal("expected success=true")
	}
	if resp.Json == "" {
		t.Fatal("expected non-empty audit JSON")
	}

	var audit map[string]any
	if err := json.Unmarshal([]byte(resp.Json), &audit); err != nil {
		t.Fatalf("unmarshal audit: %v", err)
	}
	if audit["entries"] == nil {
		t.Fatal("expected entries in audit response")
	}
}

func TestQueryAuditNoAuth(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	_, err := env.client.QueryAudit(context.Background(), &pb.QueryAuditRequest{})
	if err == nil {
		t.Fatal("expected error for missing auth")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.Unauthenticated {
		t.Fatalf("expected Unauthenticated, got %v", st.Code())
	}
}

func TestListCheckpoints(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	resp, err := env.client.ListCheckpoints(context.Background(), &pb.ListCheckpointsRequest{})
	if err != nil {
		t.Fatalf("ListCheckpoints() error: %v", err)
	}
	if resp.Json == "" {
		t.Fatal("expected non-empty checkpoints JSON")
	}

	var result map[string]any
	if err := json.Unmarshal([]byte(resp.Json), &result); err != nil {
		t.Fatalf("unmarshal checkpoints: %v", err)
	}
	if result["checkpoints"] == nil {
		t.Fatal("expected checkpoints in response")
	}
}

func TestGetCheckpointNotFound(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	_, err := env.client.GetCheckpoint(context.Background(), &pb.GetCheckpointRequest{
		Id: "nonexistent-checkpoint",
	})
	if err == nil {
		t.Fatal("expected error for nonexistent checkpoint")
	}
	st, ok := status.FromError(err)
	if !ok {
		t.Fatalf("expected gRPC status error, got %v", err)
	}
	if st.Code() != codes.NotFound {
		t.Fatalf("expected NotFound, got %v", st.Code())
	}
}

func TestGetCheckpointConsistencyFrom(t *testing.T) {
	env := newTestEnv(t)
	defer env.stop()

	// Issue token and invoke to create audit entries.
	tokResp, err := env.client.IssueToken(
		metadata.AppendToOutgoingContext(context.Background(), "authorization", "Bearer test-api-key"),
		&pb.IssueTokenRequest{Subject: "agent:test", Scope: []string{"test"}, Capability: "echo"},
	)
	if err != nil {
		t.Fatalf("IssueToken: %v", err)
	}
	jwt := tokResp.Token

	ctx := metadata.AppendToOutgoingContext(context.Background(), "authorization", "Bearer "+jwt)
	env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: `{"message":"a"}`,
	})

	// Create first checkpoint.
	cp1, err := env.svc.CreateCheckpoint()
	if err != nil || cp1 == nil {
		t.Fatalf("first CreateCheckpoint: %v", err)
	}

	// More invocations.
	env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: `{"message":"b"}`,
	})
	env.client.Invoke(ctx, &pb.InvokeRequest{
		Capability:     "echo",
		ParametersJson: `{"message":"c"}`,
	})

	// Create second checkpoint.
	cp2, err := env.svc.CreateCheckpoint()
	if err != nil || cp2 == nil {
		t.Fatalf("second CreateCheckpoint: %v", err)
	}

	// Get checkpoint 2 with consistency proof from checkpoint 1.
	resp, err := env.client.GetCheckpoint(context.Background(), &pb.GetCheckpointRequest{
		Id:              cp2.CheckpointID,
		ConsistencyFrom: cp1.CheckpointID,
	})
	if err != nil {
		t.Fatalf("GetCheckpoint with consistency_from: %v", err)
	}

	// The response JSON should contain "consistency_proof".
	if !strings.Contains(resp.Json, "consistency_proof") {
		t.Errorf("expected consistency_proof in response, got: %s", resp.Json[:min(200, len(resp.Json))])
	}
}
