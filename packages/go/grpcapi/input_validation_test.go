// Parameter validation over gRPC (SPEC.md §6.3): the refusal is in the
// response message, for Invoke and for InvokeStream.

package grpcapi

import (
	"context"
	"encoding/json"
	"io"
	"net"
	"reflect"
	"sync/atomic"
	"testing"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"github.com/anip-protocol/anip/packages/go/core"
	pb "github.com/anip-protocol/anip/packages/go/grpcapi/proto/anip/v1"
	"github.com/anip-protocol/anip/packages/go/service"
)

func newValidationGrpcEnv(t *testing.T) (pb.AnipServiceClient, string, *atomic.Int32) {
	t.Helper()
	handled := &atomic.Int32{}
	svc := service.New(service.Config{
		ServiceID: "test-grpc-service",
		Capabilities: []service.CapabilityDef{{
			Declaration: core.CapabilityDeclaration{
				Name:            "watch_fares",
				Description:     "Watch fares on a route",
				ContractVersion: "1.0",
				Inputs: []core.CapabilityInput{
					{Name: "route", Type: "string", Required: true},
					{Name: "limit", Type: "integer", Required: false},
				},
				Output:        core.CapabilityOutput{Type: "object", Fields: []string{"count"}},
				SideEffect:    core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
				MinimumScope:  []string{"travel.search"},
				ResponseModes: []string{"unary", "streaming"},
			},
			Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
				handled.Add(1)
				return map[string]any{"count": 0}, nil
			},
		}},
		Storage:                  ":memory:",
		Trust:                    "signed",
		RetentionIntervalSeconds: -1,
	})
	if err := svc.Start(); err != nil {
		t.Fatalf("Start() error: %v", err)
	}
	lis, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		svc.Shutdown()
		t.Fatalf("Listen error: %v", err)
	}
	server := grpc.NewServer()
	pb.RegisterAnipServiceServer(server, NewAnipGrpcServer(svc))
	go func() { _ = server.Serve(lis) }()
	conn, err := grpc.NewClient(lis.Addr().String(), grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		server.GracefulStop()
		svc.Shutdown()
		t.Fatalf("Dial error: %v", err)
	}
	t.Cleanup(func() {
		conn.Close()
		server.GracefulStop()
		svc.Shutdown()
	})
	return pb.NewAnipServiceClient(conn), issueCapabilityToken(t, svc, []string{"travel.search"}, "watch_fares"), handled
}

func assertInvalidParametersGrpcFailure(t *testing.T, failure *pb.AnipFailure, detail string) {
	t.Helper()
	if failure == nil {
		t.Fatal("no failure in the response message")
	}
	if failure.Type != core.FailureInvalidParameters || failure.Detail != detail || failure.Retry {
		t.Fatalf("failure = type %q detail %q retry %v, want invalid_parameters %q retry false",
			failure.Type, failure.Detail, failure.Retry, detail)
	}
	var resolution map[string]any
	if err := json.Unmarshal([]byte(failure.ResolutionJson), &resolution); err != nil {
		t.Fatalf("resolution_json %q: %v", failure.ResolutionJson, err)
	}
	want := map[string]any{
		"action":         "retry_now",
		"recovery_class": "retry_now",
		"requires":       "parameters that match the capability's declared inputs",
	}
	if !reflect.DeepEqual(resolution, want) {
		t.Fatalf("resolution = %#v, want %#v", resolution, want)
	}
}

func TestInvokeInvalidParameters(t *testing.T) {
	client, jwt, handled := newValidationGrpcEnv(t)
	ctx := withBearer(context.Background(), jwt)

	cases := []struct {
		name, parametersJSON, detail string
	}{
		{"no parameters", "", "watch_fares is missing required input(s): route"},
		{"missing", `{"limit": 3}`, "watch_fares is missing required input(s): route"},
		{"null", `{"route": null}`, "watch_fares is missing required input(s): route"},
		{"wrong type", `{"route": ["SEA"], "limit": true}`,
			"watch_fares has invalid input(s): 'route' must be string, got array; 'limit' must be integer, got boolean"},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			resp, err := client.Invoke(ctx, &pb.InvokeRequest{
				Capability:        "watch_fares",
				ParametersJson:    tc.parametersJSON,
				ClientReferenceId: "ref-1",
			})
			if err != nil {
				t.Fatalf("Invoke() error: %v", err)
			}
			if resp.Success || resp.ResultJson != "" {
				t.Fatalf("expected a refusal without a result, got %v", resp)
			}
			assertInvalidParametersGrpcFailure(t, resp.Failure, tc.detail)
			if resp.InvocationId == "" || resp.ClientReferenceId != "ref-1" {
				t.Fatalf("invocation_id / client_reference_id missing on the refusal: %v", resp)
			}
		})
	}
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

func TestInvokeStreamInvalidParameters(t *testing.T) {
	client, jwt, handled := newValidationGrpcEnv(t)
	ctx := withBearer(context.Background(), jwt)

	stream, err := client.InvokeStream(ctx, &pb.InvokeRequest{
		Capability:     "watch_fares",
		ParametersJson: `{"limit": "ten"}`,
	})
	if err != nil {
		t.Fatalf("InvokeStream() error: %v", err)
	}
	var failed *pb.FailedEvent
	events := 0
	for {
		event, err := stream.Recv()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("Recv() error: %v", err)
		}
		events++
		if e, ok := event.Event.(*pb.InvokeEvent_Failed); ok {
			failed = e.Failed
		}
	}
	if events != 1 || failed == nil {
		t.Fatalf("expected exactly one failed event, got %d events (failed=%v)", events, failed)
	}
	assertInvalidParametersGrpcFailure(t, failed.Failure, "watch_fares is missing required input(s): route")
	if handled.Load() != 0 {
		t.Fatal("the handler ran for a refused invocation")
	}
}

// invalid_parameters at IssueApprovalGrant carries the retry_now resolution too.
func TestIssueApprovalGrantInvalidRequestHasRetryNowResolution(t *testing.T) {
	client, jwt, _ := newValidationGrpcEnv(t)
	resp, err := client.IssueApprovalGrant(withBearer(context.Background(), jwt), &pb.IssueApprovalGrantRequest{
		GrantType: core.GrantTypeOneTime,
	})
	if err != nil {
		t.Fatalf("IssueApprovalGrant() error: %v", err)
	}
	if resp.Success || resp.Failure == nil || resp.Failure.Type != core.FailureInvalidParameters || resp.Failure.Retry {
		t.Fatalf("got %v, want invalid_parameters retry=false", resp)
	}
	var resolution map[string]any
	if err := json.Unmarshal([]byte(resp.Failure.ResolutionJson), &resolution); err != nil {
		t.Fatalf("resolution_json %q: %v", resp.Failure.ResolutionJson, err)
	}
	if resolution["action"] != "retry_now" || resolution["recovery_class"] != "retry_now" {
		t.Fatalf("resolution = %v, want retry_now / retry_now", resolution)
	}
}
