// Storage tests for v0.23 approval requests + grants.
//
// Mirrors anip-server/tests/test_v023_storage.py and the TS equivalent in
// packages/typescript/server/tests/v023-storage.test.ts. Covers:
//   - StoreApprovalRequest / GetApprovalRequest round-trip
//   - StoreApprovalRequest idempotency on identical content; conflict on diff
//   - ApproveRequestAndStoreGrant happy path + every failure reason
//   - StoreGrant / GetGrant round-trip
//   - TryReserveGrant happy path + grant_consumed + grant_expired + grant_not_found
//   - Concurrent issuance (exactly-one-succeeds invariant)
//   - Concurrent reservation (max_uses respected under contention)
//
// Subtests run against SQLite (the only Go-native storage backend in this
// PR). When a Postgres DSN is set via ANIP_TEST_POSTGRES_DSN we additionally
// exercise the same matrix against PostgresStorage.

package server

import (
	"fmt"
	"os"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
)

// --- Builders --------------------------------------------------------------

func nowISO() string {
	return time.Now().UTC().Format(time.RFC3339Nano)
}

func futureISO(seconds int) string {
	return time.Now().UTC().Add(time.Duration(seconds) * time.Second).Format(time.RFC3339Nano)
}

func pastISO(seconds int) string {
	return time.Now().UTC().Add(-time.Duration(seconds) * time.Second).Format(time.RFC3339Nano)
}

type approvalRequestOpts struct {
	requestID  string
	capability string
	expiresAt  string
}

func makeApprovalRequest(opts approvalRequestOpts) *core.ApprovalRequest {
	if opts.requestID == "" {
		opts.requestID = "apr_test"
	}
	if opts.capability == "" {
		opts.capability = "finance.transfer_funds"
	}
	if opts.expiresAt == "" {
		opts.expiresAt = futureISO(900)
	}
	return &core.ApprovalRequest{
		ApprovalRequestID:         opts.requestID,
		Capability:                opts.capability,
		Scope:                     []string{"finance.write"},
		Requester:                 map[string]any{"principal": "user_123"},
		Preview:                   map[string]any{"amount": float64(50000)},
		PreviewDigest:             "sha256:preview",
		RequestedParameters:       map[string]any{"amount": float64(50000)},
		RequestedParametersDigest: "sha256:params",
		GrantPolicy: core.GrantPolicy{
			AllowedGrantTypes: []string{"one_time"},
			DefaultGrantType:  "one_time",
			ExpiresInSeconds:  900,
			MaxUses:           1,
		},
		Status:    core.ApprovalRequestStatusPending,
		CreatedAt: nowISO(),
		ExpiresAt: opts.expiresAt,
	}
}

type grantOpts struct {
	grantID   string
	requestID string
	grantType string
	maxUses   int
	sessionID string
	expiresAt string
}

func makeGrant(opts grantOpts) *core.ApprovalGrant {
	if opts.grantID == "" {
		opts.grantID = "grant_test"
	}
	if opts.requestID == "" {
		opts.requestID = "apr_test"
	}
	if opts.grantType == "" {
		opts.grantType = core.GrantTypeOneTime
	}
	if opts.maxUses == 0 {
		opts.maxUses = 1
	}
	if opts.expiresAt == "" {
		opts.expiresAt = futureISO(900)
	}
	return &core.ApprovalGrant{
		GrantID:                  opts.grantID,
		ApprovalRequestID:        opts.requestID,
		GrantType:                opts.grantType,
		Capability:               "finance.transfer_funds",
		Scope:                    []string{"finance.write"},
		ApprovedParametersDigest: "sha256:params",
		PreviewDigest:            "sha256:preview",
		Requester:                map[string]any{"principal": "user_123"},
		Approver:                 map[string]any{"principal": "manager_456"},
		IssuedAt:                 nowISO(),
		ExpiresAt:                opts.expiresAt,
		MaxUses:                  opts.maxUses,
		UseCount:                 0,
		SessionID:                opts.sessionID,
		Signature:                "sig_test",
	}
}

// ensureRequestFor seeds the parent ApprovalRequest so a direct StoreGrant
// satisfies the FK on approval_request_id.
func ensureRequestFor(t *testing.T, store Storage, requestID string) {
	t.Helper()
	if err := store.StoreApprovalRequest(makeApprovalRequest(approvalRequestOpts{requestID: requestID})); err != nil {
		t.Fatalf("seed approval request: %v", err)
	}
}

// --- Backend matrix --------------------------------------------------------

// storageBackend describes how to construct a fresh Storage for one subtest.
type storageBackend struct {
	name string
	open func(t *testing.T) Storage
}

func storageBackends(t *testing.T) []storageBackend {
	t.Helper()
	backends := []storageBackend{
		{
			name: "sqlite",
			open: func(t *testing.T) Storage {
				t.Helper()
				s, err := NewSQLiteStorage(":memory:")
				if err != nil {
					t.Fatalf("NewSQLiteStorage: %v", err)
				}
				t.Cleanup(func() { s.Close() })
				return s
			},
		},
	}
	// Optional: Postgres when DSN is supplied.
	if dsn := getOptionalPostgresDSN(); dsn != "" {
		backends = append(backends, storageBackend{
			name: "postgres",
			open: func(t *testing.T) Storage {
				t.Helper()
				cleanPostgres(t, dsn)
				s, err := NewPostgresStorage(dsn)
				if err != nil {
					t.Fatalf("NewPostgresStorage: %v", err)
				}
				t.Cleanup(func() { s.Close() })
				return s
			},
		})
	}
	return backends
}

func getOptionalPostgresDSN() string {
	// Mirror postgres_test.go behaviour but non-fatal when unset.
	v, ok := lookupEnv("ANIP_TEST_POSTGRES_DSN")
	if !ok {
		return ""
	}
	return v
}

// lookupEnv is a thin wrapper so the matrix builder doesn't have to import
// os inline.
func lookupEnv(key string) (string, bool) {
	return os.LookupEnv(key)
}

// --- Round-trip + idempotency ---------------------------------------------

func TestV023StoreApprovalRequestRoundTrip(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			req := makeApprovalRequest(approvalRequestOpts{})
			if err := s.StoreApprovalRequest(req); err != nil {
				t.Fatalf("StoreApprovalRequest: %v", err)
			}
			loaded, err := s.GetApprovalRequest("apr_test")
			if err != nil {
				t.Fatalf("GetApprovalRequest: %v", err)
			}
			if loaded == nil {
				t.Fatal("expected a row, got nil")
			}
			if loaded.ApprovalRequestID != "apr_test" {
				t.Errorf("ApprovalRequestID = %q, want %q", loaded.ApprovalRequestID, "apr_test")
			}
			if loaded.Capability != "finance.transfer_funds" {
				t.Errorf("Capability = %q", loaded.Capability)
			}
			if loaded.Status != core.ApprovalRequestStatusPending {
				t.Errorf("Status = %q, want pending", loaded.Status)
			}
			if len(loaded.Scope) != 1 || loaded.Scope[0] != "finance.write" {
				t.Errorf("Scope = %v", loaded.Scope)
			}
			if loaded.GrantPolicy.ExpiresInSeconds != 900 {
				t.Errorf("ExpiresInSeconds = %d, want 900", loaded.GrantPolicy.ExpiresInSeconds)
			}
		})
	}
}

func TestV023GetApprovalRequestMissing(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			loaded, err := s.GetApprovalRequest("nope")
			if err != nil {
				t.Fatalf("GetApprovalRequest: %v", err)
			}
			if loaded != nil {
				t.Fatalf("expected nil, got %+v", loaded)
			}
		})
	}
}

func TestV023StoreApprovalRequestIdempotentOnIdentical(t *testing.T) {
	// SPEC.md §4.7: re-storing identical content under same id is a no-op.
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			req := makeApprovalRequest(approvalRequestOpts{})
			if err := s.StoreApprovalRequest(req); err != nil {
				t.Fatalf("first StoreApprovalRequest: %v", err)
			}
			// Second store with the exact same content must not raise.
			if err := s.StoreApprovalRequest(req); err != nil {
				t.Fatalf("idempotent second StoreApprovalRequest: %v", err)
			}
			loaded, err := s.GetApprovalRequest("apr_test")
			if err != nil {
				t.Fatalf("GetApprovalRequest: %v", err)
			}
			if loaded == nil || loaded.ApprovalRequestID != "apr_test" {
				t.Fatalf("unexpected loaded value: %+v", loaded)
			}
		})
	}
}

func TestV023StoreApprovalRequestConflictOnDifferentContent(t *testing.T) {
	// SPEC.md §4.7: re-storing different content under same id is an error.
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			req := makeApprovalRequest(approvalRequestOpts{})
			if err := s.StoreApprovalRequest(req); err != nil {
				t.Fatalf("first StoreApprovalRequest: %v", err)
			}
			mutated := makeApprovalRequest(approvalRequestOpts{})
			mutated.Preview = map[string]any{"amount": float64(99999)}
			err := s.StoreApprovalRequest(mutated)
			if err == nil {
				t.Fatal("expected conflict error, got nil")
			}
			// Original content preserved.
			loaded, err := s.GetApprovalRequest("apr_test")
			if err != nil {
				t.Fatalf("GetApprovalRequest after conflict: %v", err)
			}
			amt, _ := loaded.Preview["amount"].(float64)
			if amt != 50000 {
				t.Fatalf("preview was overwritten: amount=%v", loaded.Preview["amount"])
			}
		})
	}
}

func TestV023StoreAndGetGrantRoundTrip(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			g := makeGrant(grantOpts{})
			if err := s.StoreGrant(g); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			loaded, err := s.GetGrant("grant_test")
			if err != nil {
				t.Fatalf("GetGrant: %v", err)
			}
			if loaded == nil {
				t.Fatal("expected grant, got nil")
			}
			if loaded.GrantID != "grant_test" {
				t.Errorf("GrantID = %q", loaded.GrantID)
			}
			if loaded.ApprovalRequestID != "apr_test" {
				t.Errorf("ApprovalRequestID = %q", loaded.ApprovalRequestID)
			}
			if loaded.UseCount != 0 {
				t.Errorf("UseCount = %d, want 0", loaded.UseCount)
			}
		})
	}
}

// --- ApproveRequestAndStoreGrant ------------------------------------------

func TestV023ApproveRequestAndStoreGrantHappyPath(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			if err := s.StoreApprovalRequest(makeApprovalRequest(approvalRequestOpts{})); err != nil {
				t.Fatalf("StoreApprovalRequest: %v", err)
			}
			res, err := s.ApproveRequestAndStoreGrant(
				"apr_test",
				makeGrant(grantOpts{}),
				map[string]any{"principal": "manager_456"},
				nowISO(), nowISO(),
			)
			if err != nil {
				t.Fatalf("ApproveRequestAndStoreGrant: %v", err)
			}
			if !res.OK {
				t.Fatalf("expected OK=true, got reason=%q", res.Reason)
			}
			if res.Grant == nil || res.Grant.GrantID != "grant_test" {
				t.Fatalf("returned grant = %+v", res.Grant)
			}
			loadedReq, err := s.GetApprovalRequest("apr_test")
			if err != nil {
				t.Fatalf("GetApprovalRequest: %v", err)
			}
			if loadedReq.Status != core.ApprovalRequestStatusApproved {
				t.Errorf("Status = %q, want approved", loadedReq.Status)
			}
			principal, _ := loadedReq.Approver["principal"].(string)
			if principal != "manager_456" {
				t.Errorf("Approver.principal = %q, want manager_456", principal)
			}
			loadedGrant, err := s.GetGrant("grant_test")
			if err != nil {
				t.Fatalf("GetGrant: %v", err)
			}
			if loadedGrant == nil {
				t.Fatal("grant should be persisted")
			}
		})
	}
}

func TestV023ApproveRequestNotFound(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			res, err := s.ApproveRequestAndStoreGrant(
				"nope", makeGrant(grantOpts{}),
				map[string]any{}, nowISO(), nowISO(),
			)
			if err != nil {
				t.Fatalf("ApproveRequestAndStoreGrant: %v", err)
			}
			if res.OK {
				t.Fatal("expected OK=false")
			}
			if res.Reason != "approval_request_not_found" {
				t.Errorf("Reason = %q", res.Reason)
			}
		})
	}
}

func TestV023ApproveRequestAlreadyDecided(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			if err := s.StoreApprovalRequest(makeApprovalRequest(approvalRequestOpts{})); err != nil {
				t.Fatalf("StoreApprovalRequest: %v", err)
			}
			first, err := s.ApproveRequestAndStoreGrant(
				"apr_test", makeGrant(grantOpts{grantID: "g1"}),
				map[string]any{"principal": "u2"}, nowISO(), nowISO(),
			)
			if err != nil || !first.OK {
				t.Fatalf("first approval failed: err=%v reason=%q", err, first.Reason)
			}
			res, err := s.ApproveRequestAndStoreGrant(
				"apr_test", makeGrant(grantOpts{grantID: "g2"}),
				map[string]any{"principal": "u3"}, nowISO(), nowISO(),
			)
			if err != nil {
				t.Fatalf("second ApproveRequestAndStoreGrant: %v", err)
			}
			if res.OK {
				t.Fatal("expected OK=false on second approve")
			}
			if res.Reason != "approval_request_already_decided" {
				t.Errorf("Reason = %q, want approval_request_already_decided", res.Reason)
			}
		})
	}
}

func TestV023ApproveRequestExpired(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			req := makeApprovalRequest(approvalRequestOpts{expiresAt: pastISO(1)})
			if err := s.StoreApprovalRequest(req); err != nil {
				t.Fatalf("StoreApprovalRequest: %v", err)
			}
			res, err := s.ApproveRequestAndStoreGrant(
				"apr_test", makeGrant(grantOpts{}),
				map[string]any{"principal": "u2"}, nowISO(), nowISO(),
			)
			if err != nil {
				t.Fatalf("ApproveRequestAndStoreGrant: %v", err)
			}
			if res.OK {
				t.Fatal("expected OK=false")
			}
			if res.Reason != "approval_request_expired" {
				t.Errorf("Reason = %q, want approval_request_expired", res.Reason)
			}
		})
	}
}

func TestV023ConcurrentApproveRequestAndStoreGrant(t *testing.T) {
	// Concurrent approval attempts: exactly 1 succeeds, N-1 receive
	// approval_request_already_decided.
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			if err := s.StoreApprovalRequest(makeApprovalRequest(approvalRequestOpts{})); err != nil {
				t.Fatalf("StoreApprovalRequest: %v", err)
			}
			const n = 5
			var wg sync.WaitGroup
			var successes int32
			var rejected int32
			results := make([]string, n)
			for i := 0; i < n; i++ {
				wg.Add(1)
				go func(idx int) {
					defer wg.Done()
					res, err := s.ApproveRequestAndStoreGrant(
						"apr_test",
						makeGrant(grantOpts{grantID: fmt.Sprintf("g%d", idx)}),
						map[string]any{"principal": fmt.Sprintf("u%d", idx)},
						nowISO(), nowISO(),
					)
					if err != nil {
						t.Errorf("goroutine %d: %v", idx, err)
						return
					}
					if res.OK {
						atomic.AddInt32(&successes, 1)
					} else {
						atomic.AddInt32(&rejected, 1)
						results[idx] = res.Reason
					}
				}(i)
			}
			wg.Wait()
			if got := atomic.LoadInt32(&successes); got != 1 {
				t.Errorf("successes = %d, want 1", got)
			}
			if got := atomic.LoadInt32(&rejected); got != n-1 {
				t.Errorf("rejected = %d, want %d", got, n-1)
			}
			for i, r := range results {
				if r == "" {
					continue
				}
				if r != "approval_request_already_decided" {
					t.Errorf("rejection[%d] = %q, want approval_request_already_decided", i, r)
				}
			}
			loaded, err := s.GetApprovalRequest("apr_test")
			if err != nil {
				t.Fatalf("GetApprovalRequest: %v", err)
			}
			if loaded.Status != core.ApprovalRequestStatusApproved {
				t.Errorf("Status = %q, want approved", loaded.Status)
			}
		})
	}
}

// --- TryReserveGrant ------------------------------------------------------

func TestV023TryReserveGrantHappyPath(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			if err := s.StoreGrant(makeGrant(grantOpts{})); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			res, err := s.TryReserveGrant("grant_test", nowISO())
			if err != nil {
				t.Fatalf("TryReserveGrant: %v", err)
			}
			if !res.OK {
				t.Fatalf("expected OK=true, got reason=%q", res.Reason)
			}
			if res.Grant == nil || res.Grant.UseCount != 1 {
				t.Fatalf("UseCount = %d (Grant=%+v), want 1", res.Grant.UseCount, res.Grant)
			}
		})
	}
}

func TestV023TryReserveGrantNotFound(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			res, err := s.TryReserveGrant("nope", nowISO())
			if err != nil {
				t.Fatalf("TryReserveGrant: %v", err)
			}
			if res.OK {
				t.Fatal("expected OK=false")
			}
			if res.Reason != "grant_not_found" {
				t.Errorf("Reason = %q", res.Reason)
			}
		})
	}
}

func TestV023TryReserveGrantExpired(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			if err := s.StoreGrant(makeGrant(grantOpts{expiresAt: pastISO(1)})); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			res, err := s.TryReserveGrant("grant_test", nowISO())
			if err != nil {
				t.Fatalf("TryReserveGrant: %v", err)
			}
			if res.OK {
				t.Fatal("expected OK=false")
			}
			if res.Reason != "grant_expired" {
				t.Errorf("Reason = %q, want grant_expired", res.Reason)
			}
		})
	}
}

func TestV023TryReserveGrantOneTimeConsumed(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			if err := s.StoreGrant(makeGrant(grantOpts{maxUses: 1})); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			first, err := s.TryReserveGrant("grant_test", nowISO())
			if err != nil || !first.OK {
				t.Fatalf("first reservation: err=%v ok=%v", err, first.OK)
			}
			second, err := s.TryReserveGrant("grant_test", nowISO())
			if err != nil {
				t.Fatalf("second reservation: %v", err)
			}
			if second.OK {
				t.Fatal("expected OK=false on second use")
			}
			if second.Reason != "grant_consumed" {
				t.Errorf("Reason = %q, want grant_consumed", second.Reason)
			}
		})
	}
}

func TestV023TryReserveGrantSessionBoundMaxUses(t *testing.T) {
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			g := makeGrant(grantOpts{
				grantType: core.GrantTypeSessionBound,
				maxUses:   3,
				sessionID: "sess_1",
			})
			if err := s.StoreGrant(g); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			for i := 0; i < 3; i++ {
				r, err := s.TryReserveGrant("grant_test", nowISO())
				if err != nil {
					t.Fatalf("reservation %d: %v", i, err)
				}
				if !r.OK {
					t.Fatalf("reservation %d: ok=false reason=%q", i, r.Reason)
				}
			}
			fourth, err := s.TryReserveGrant("grant_test", nowISO())
			if err != nil {
				t.Fatalf("fourth reservation: %v", err)
			}
			if fourth.OK {
				t.Fatal("expected fourth reservation to fail")
			}
			if fourth.Reason != "grant_consumed" {
				t.Errorf("Reason = %q, want grant_consumed", fourth.Reason)
			}
		})
	}
}

func TestV023ConcurrentTryReserveGrantOneTime(t *testing.T) {
	// N parallel reservations on a one-use grant: exactly 1 ok, N-1
	// grant_consumed. Security-critical atomicity test for §4.8 Phase B.
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			if err := s.StoreGrant(makeGrant(grantOpts{maxUses: 1})); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			const n = 10
			var wg sync.WaitGroup
			var successes int32
			var consumed int32
			for i := 0; i < n; i++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					res, err := s.TryReserveGrant("grant_test", nowISO())
					if err != nil {
						t.Errorf("TryReserveGrant: %v", err)
						return
					}
					if res.OK {
						atomic.AddInt32(&successes, 1)
					} else if res.Reason == "grant_consumed" {
						atomic.AddInt32(&consumed, 1)
					} else {
						t.Errorf("unexpected reason %q", res.Reason)
					}
				}()
			}
			wg.Wait()
			if got := atomic.LoadInt32(&successes); got != 1 {
				t.Errorf("successes = %d, want 1", got)
			}
			if got := atomic.LoadInt32(&consumed); got != n-1 {
				t.Errorf("consumed = %d, want %d", got, n-1)
			}
		})
	}
}

func TestV023ConcurrentTryReserveSessionBoundRespectsMaxUses(t *testing.T) {
	// Session-bound grant with max_uses=3 and N=10 parallel reservations:
	// exactly 3 ok, 7 grant_consumed. use_count must never exceed max_uses.
	for _, backend := range storageBackends(t) {
		t.Run(backend.name, func(t *testing.T) {
			s := backend.open(t)
			ensureRequestFor(t, s, "apr_test")
			g := makeGrant(grantOpts{
				grantType: core.GrantTypeSessionBound,
				maxUses:   3,
				sessionID: "sess_1",
			})
			if err := s.StoreGrant(g); err != nil {
				t.Fatalf("StoreGrant: %v", err)
			}
			const n = 10
			var wg sync.WaitGroup
			var successes int32
			var consumed int32
			for i := 0; i < n; i++ {
				wg.Add(1)
				go func() {
					defer wg.Done()
					res, err := s.TryReserveGrant("grant_test", nowISO())
					if err != nil {
						t.Errorf("TryReserveGrant: %v", err)
						return
					}
					if res.OK {
						atomic.AddInt32(&successes, 1)
					} else if res.Reason == "grant_consumed" {
						atomic.AddInt32(&consumed, 1)
					} else {
						t.Errorf("unexpected reason %q", res.Reason)
					}
				}()
			}
			wg.Wait()
			if got := atomic.LoadInt32(&successes); got != 3 {
				t.Errorf("successes = %d, want 3", got)
			}
			if got := atomic.LoadInt32(&consumed); got != n-3 {
				t.Errorf("consumed = %d, want %d", got, n-3)
			}
			// Defense-in-depth: persisted use_count must be exactly max_uses.
			loaded, err := s.GetGrant("grant_test")
			if err != nil {
				t.Fatalf("GetGrant: %v", err)
			}
			if loaded.UseCount > loaded.MaxUses {
				t.Errorf("use_count=%d exceeded max_uses=%d", loaded.UseCount, loaded.MaxUses)
			}
		})
	}
}

// --- Defense-in-depth ------------------------------------------------------

func TestV023GrantsUniqueApprovalRequestIDSqlite(t *testing.T) {
	// Defense-in-depth: a second approval attempt against an already-approved
	// request must fail with approval_request_already_decided. Even if a
	// flawed implementation bypassed the conditional UPDATE, the UNIQUE
	// constraint on approval_request_id would still trip the INSERT, and the
	// error path translates that to approval_request_already_decided. Here we
	// drive that end-to-end via ApproveRequestAndStoreGrant.
	s, err := NewSQLiteStorage(":memory:")
	if err != nil {
		t.Fatalf("NewSQLiteStorage: %v", err)
	}
	t.Cleanup(func() { s.Close() })

	if err := s.StoreApprovalRequest(makeApprovalRequest(approvalRequestOpts{requestID: "apr_x"})); err != nil {
		t.Fatalf("StoreApprovalRequest: %v", err)
	}
	r1, err := s.ApproveRequestAndStoreGrant(
		"apr_x",
		makeGrant(grantOpts{grantID: "g1", requestID: "apr_x"}),
		map[string]any{"principal": "u1"}, nowISO(), nowISO(),
	)
	if err != nil || !r1.OK {
		t.Fatalf("first approve failed: err=%v reason=%q", err, r1.Reason)
	}
	r2, err := s.ApproveRequestAndStoreGrant(
		"apr_x",
		makeGrant(grantOpts{grantID: "g2", requestID: "apr_x"}),
		map[string]any{"principal": "u2"}, nowISO(), nowISO(),
	)
	if err != nil {
		t.Fatalf("second approve: %v", err)
	}
	if r2.OK {
		t.Fatal("expected OK=false")
	}
	if r2.Reason != "approval_request_already_decided" {
		t.Errorf("Reason = %q, want approval_request_already_decided", r2.Reason)
	}
	stored1, err := s.GetGrant("g1")
	if err != nil {
		t.Fatalf("GetGrant g1: %v", err)
	}
	if stored1 == nil {
		t.Error("g1 should be persisted")
	}
	stored2, err := s.GetGrant("g2")
	if err != nil {
		t.Fatalf("GetGrant g2: %v", err)
	}
	if stored2 != nil {
		t.Error("g2 must NOT be persisted — UNIQUE constraint should block it")
	}
}
