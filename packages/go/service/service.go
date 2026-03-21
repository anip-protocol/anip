// Package service orchestrates core, crypto, and server into a usable ANIP runtime.
package service

import (
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/crypto"
	"github.com/anip-protocol/anip/packages/go/server"
)

// Config holds the configuration for an ANIP service.
type Config struct {
	ServiceID    string
	Capabilities []CapabilityDef
	Storage      string // "sqlite:///path" or ":memory:"
	Trust        string // "signed" or "anchored"
	KeyPath      string
	Authenticate func(bearer string) (principal string, ok bool)

	// Observability hooks (optional). Nil means no hooks.
	Hooks *ObservabilityHooks

	// CheckpointPolicy configures automatic checkpoint scheduling.
	// If nil, no automatic checkpoints are created.
	CheckpointPolicy *CheckpointPolicy

	// RetentionIntervalSeconds sets how often the retention sweep runs (default 60).
	// Set to -1 to disable automatic retention enforcement.
	RetentionIntervalSeconds int
}

// CapabilityDef binds a capability declaration to a handler function.
type CapabilityDef struct {
	Declaration core.CapabilityDeclaration
	Handler     func(ctx *InvocationContext, params map[string]any) (map[string]any, error)
}

// InvocationContext provides the handler with delegation context.
type InvocationContext struct {
	Token             *core.DelegationToken
	RootPrincipal     string
	Subject           string
	Scopes            []string
	DelegationChain   []string
	InvocationID      string
	ClientReferenceID string
	costActual        *core.CostActual
	EmitProgress      func(payload map[string]any) error
}

// SetCostActual sets the actual cost incurred by the invocation.
func (ctx *InvocationContext) SetCostActual(cost *core.CostActual) {
	ctx.costActual = cost
}

// InvokeOpts holds optional parameters for invocation.
type InvokeOpts struct {
	ClientReferenceID string
	Stream            bool
}

// CheckpointPolicy configures automatic checkpoint creation.
type CheckpointPolicy struct {
	IntervalSeconds int // how often to check (default 60)
	MinEntries      int // minimum new entries before creating a checkpoint
}

// HealthReport describes the current health of the service.
type HealthReport struct {
	Status  string        `json:"status"` // "healthy", "degraded", "unhealthy"
	Storage StorageHealth `json:"storage"`
	Uptime  string        `json:"uptime"`
	Version string        `json:"version"`
}

// StorageHealth describes the health of the storage backend.
type StorageHealth struct {
	Connected bool   `json:"connected"`
	Type      string `json:"type"` // "sqlite" or "postgres"
}

// Service is the main ANIP service runtime.
type Service struct {
	serviceID    string
	trustLevel   string
	capabilities map[string]CapabilityDef
	storage      server.Storage
	keys         *crypto.KeyManager
	authenticate func(bearer string) (string, bool)
	storageDSN   string
	keyPath      string
	hooks        *ObservabilityHooks
	startedAt    time.Time

	// Background goroutine management
	checkpointPolicy         *CheckpointPolicy
	retentionIntervalSeconds int
	retentionRunning         bool
	stopCh                   chan struct{}
	wg                       sync.WaitGroup
}

// New creates a new Service from the given configuration.
// Call Start() to initialize storage and keys before use.
func New(cfg Config) *Service {
	caps := make(map[string]CapabilityDef, len(cfg.Capabilities))
	for _, c := range cfg.Capabilities {
		caps[c.Declaration.Name] = c
	}

	trust := cfg.Trust
	if trust == "" {
		trust = "signed"
	}

	storageDSN := cfg.Storage
	if storageDSN == "" {
		storageDSN = ":memory:"
	}

	retentionInterval := cfg.RetentionIntervalSeconds
	if retentionInterval == 0 {
		retentionInterval = 60 // default
	}
	// -1 means disabled
	if retentionInterval < 0 {
		retentionInterval = 0
	}

	return &Service{
		serviceID:                cfg.ServiceID,
		trustLevel:               trust,
		capabilities:             caps,
		authenticate:             cfg.Authenticate,
		storageDSN:               storageDSN,
		keyPath:                  cfg.KeyPath,
		hooks:                    cfg.Hooks,
		checkpointPolicy:         cfg.CheckpointPolicy,
		retentionIntervalSeconds: retentionInterval,
	}
}

// Start initializes storage, loads or generates cryptographic keys,
// and starts background goroutines for retention and checkpoint scheduling.
func (s *Service) Start() error {
	if err := s.startWithDSN(s.storageDSN, s.keyPath); err != nil {
		return err
	}
	s.startedAt = time.Now()
	s.stopCh = make(chan struct{})

	// Start retention enforcement goroutine.
	if s.retentionIntervalSeconds > 0 {
		s.retentionRunning = true
		s.wg.Add(1)
		go s.runRetentionLoop()
	}

	// Start checkpoint scheduling goroutine.
	if s.checkpointPolicy != nil {
		s.wg.Add(1)
		go s.runCheckpointLoop()
	}

	return nil
}

func (s *Service) startWithDSN(storageDSN, keyPath string) error {
	// Parse storage string.
	var store server.Storage
	var err error
	if storageDSN == ":memory:" || storageDSN == "" {
		store, err = server.NewSQLiteStorage(":memory:")
	} else if strings.HasPrefix(storageDSN, "sqlite:///") {
		dbPath := strings.TrimPrefix(storageDSN, "sqlite:///")
		store, err = server.NewSQLiteStorage(dbPath)
	} else if strings.HasPrefix(storageDSN, "postgres://") || strings.HasPrefix(storageDSN, "postgresql://") {
		store, err = server.NewPostgresStorage(storageDSN)
	} else {
		return fmt.Errorf("unsupported storage: %s", storageDSN)
	}
	if err != nil {
		return fmt.Errorf("init storage: %w", err)
	}
	s.storage = store

	// Initialize keys.
	km, err := crypto.NewKeyManager(keyPath)
	if err != nil {
		return fmt.Errorf("init keys: %w", err)
	}
	s.keys = km

	return nil
}

// Shutdown stops background goroutines and releases storage resources.
// Safe to call multiple times.
func (s *Service) Shutdown() error {
	if s.stopCh != nil {
		select {
		case <-s.stopCh:
			// Already closed.
		default:
			close(s.stopCh)
		}
		s.wg.Wait()
	}
	if s.storage != nil {
		return s.storage.Close()
	}
	return nil
}

// AuthenticateBearer tries bootstrap authentication only (API keys, external auth).
// Returns the principal string and true if authenticated, or ("", false) otherwise.
func (s *Service) AuthenticateBearer(bearer string) (string, bool) {
	if s.authenticate != nil {
		return s.authenticate(bearer)
	}
	return "", false
}

// ResolveBearerToken verifies a JWT and returns the stored DelegationToken.
func (s *Service) ResolveBearerToken(jwtStr string) (*core.DelegationToken, error) {
	token, err := server.ResolveBearerToken(s.keys, s.storage, s.serviceID, jwtStr)
	if err != nil {
		if anipErr, ok := err.(*core.ANIPError); ok && s.hooks != nil && s.hooks.OnAuthFailure != nil {
			callHook(func() { s.hooks.OnAuthFailure(anipErr.ErrorType, anipErr.Detail) })
		}
		return nil, err
	}
	if s.hooks != nil && s.hooks.OnTokenResolved != nil {
		callHook(func() { s.hooks.OnTokenResolved(token.TokenID, token.Subject) })
	}
	return token, nil
}

// IssueToken issues a delegation token for the authenticated principal.
func (s *Service) IssueToken(principal string, req core.TokenRequest) (core.TokenResponse, error) {
	resp, err := server.IssueDelegationToken(s.keys, s.storage, s.serviceID, principal, req)
	if err != nil {
		return resp, err
	}
	if s.hooks != nil && s.hooks.OnTokenIssued != nil {
		callHook(func() { s.hooks.OnTokenIssued(resp.TokenID, principal, req.Capability) })
	}
	return resp, nil
}

// GetDiscovery builds the full discovery document per SPEC.md section 6.1.
func (s *Service) GetDiscovery(baseURL string) map[string]any {
	capsSummary := make(map[string]any)
	for name, cap := range s.capabilities {
		decl := cap.Declaration
		sideEffectType := ""
		if decl.SideEffect.Type != "" {
			sideEffectType = decl.SideEffect.Type
		}
		financial := false
		if decl.Cost != nil && decl.Cost.Financial != nil {
			financial = true
		}
		capsSummary[name] = map[string]any{
			"description":   decl.Description,
			"side_effect":   sideEffectType,
			"minimum_scope": decl.MinimumScope,
			"financial":     financial,
			"contract":      decl.ContractVersion,
		}
	}

	doc := map[string]any{
		"protocol":   core.ProtocolVersion,
		"compliance": "anip-compliant",
		"profile":    core.DefaultProfile,
		"auth": map[string]any{
			"delegation_token_required":  true,
			"supported_formats":          []string{"anip-v1"},
			"minimum_scope_for_discovery": "none",
		},
		"capabilities": capsSummary,
		"trust_level":  s.trustLevel,
		"posture": map[string]any{
			"audit": map[string]any{
				"retention":          "P90D",
				"retention_enforced": s.retentionRunning,
			},
			"failure_disclosure": map[string]any{
				"detail_level": "full",
			},
			"anchoring": map[string]any{
				"enabled":          false,
				"proofs_available": false,
			},
		},
		"endpoints": map[string]any{
			"manifest":    "/anip/manifest",
			"permissions": "/anip/permissions",
			"invoke":      "/anip/invoke/{capability}",
			"tokens":      "/anip/tokens",
			"audit":       "/anip/audit",
			"checkpoints": "/anip/checkpoints",
			"jwks":        "/.well-known/jwks.json",
		},
	}

	if baseURL != "" {
		doc["base_url"] = baseURL
	}

	return map[string]any{
		"anip_discovery": doc,
	}
}

// GetManifest returns the full capability manifest.
func (s *Service) GetManifest() core.ANIPManifest {
	caps := make(map[string]core.CapabilityDeclaration)
	for name, cap := range s.capabilities {
		caps[name] = cap.Declaration
	}

	return core.ANIPManifest{
		Protocol: core.ProtocolVersion,
		Profile: core.ProfileVersions{
			Core:            "1.0",
			Cost:            "1.0",
			CapabilityGraph: "1.0",
			StateSession:    "1.0",
			Observability:   "1.0",
		},
		Capabilities: caps,
		Trust: &core.TrustPosture{
			Level: s.trustLevel,
		},
		ServiceIdentity: &core.ServiceIdentity{
			ID:         s.serviceID,
			JWKSURI:    "/.well-known/jwks.json",
			IssuerMode: "first-party",
		},
	}
}

// GetSignedManifest returns the manifest as canonical JSON bytes and its detached JWS signature.
func (s *Service) GetSignedManifest() ([]byte, string) {
	manifest := s.GetManifest()

	// Serialize to canonical JSON (sorted keys, compact separators).
	// First marshal to map, then re-marshal with sorted keys.
	data, _ := json.Marshal(manifest)
	var m map[string]any
	json.Unmarshal(data, &m)
	bodyBytes, _ := json.Marshal(m)

	signature, err := crypto.SignDetachedJWS(s.keys, bodyBytes)
	if err != nil {
		return bodyBytes, ""
	}

	return bodyBytes, signature
}

// GetJWKS returns the JWKS document for this service.
func (s *Service) GetJWKS() map[string]any {
	return crypto.ToJWKS(s.keys)
}

// GetCapabilityDeclaration returns a single capability declaration by name, or nil if not found.
func (s *Service) GetCapabilityDeclaration(name string) *core.CapabilityDeclaration {
	cap, ok := s.capabilities[name]
	if !ok {
		return nil
	}
	decl := cap.Declaration
	return &decl
}

// QueryAudit queries audit entries scoped to the token's root principal.
func (s *Service) QueryAudit(token *core.DelegationToken, filters server.AuditFilters) (core.AuditResponse, error) {
	rootPrincipal := token.RootPrincipal
	if rootPrincipal == "" {
		rootPrincipal = token.Issuer
	}
	resp, err := server.QueryAudit(s.storage, rootPrincipal, filters)
	if err != nil {
		return resp, err
	}
	// Populate metadata fields expected by the protocol.
	resp.Count = len(resp.Entries)
	resp.RootPrincipal = rootPrincipal
	if filters.Capability != "" {
		cap := filters.Capability
		resp.CapabilityFilter = &cap
	}
	if filters.Since != "" {
		since := filters.Since
		resp.SinceFilter = &since
	}
	return resp, nil
}

// ListCheckpoints returns a list of checkpoints.
func (s *Service) ListCheckpoints(limit int) (core.CheckpointListResponse, error) {
	if limit <= 0 {
		limit = 50
	}

	checkpoints, err := s.storage.ListCheckpoints(limit)
	if err != nil {
		return core.CheckpointListResponse{}, fmt.Errorf("list checkpoints: %w", err)
	}

	if checkpoints == nil {
		checkpoints = []core.Checkpoint{}
	}

	return core.CheckpointListResponse{
		Checkpoints: checkpoints,
	}, nil
}

// GetCheckpoint returns a single checkpoint with optional inclusion proof.
func (s *Service) GetCheckpoint(id string, includeProof bool, leafIndex int) (*core.CheckpointDetailResponse, error) {
	cp, err := s.storage.GetCheckpointByID(id)
	if err != nil {
		return nil, fmt.Errorf("get checkpoint: %w", err)
	}
	if cp == nil {
		return nil, core.NewANIPError(core.FailureNotFound, fmt.Sprintf("checkpoint %q not found", id))
	}

	// Convert checkpoint to map for the response.
	cpData, _ := json.Marshal(cp)
	var cpMap map[string]any
	json.Unmarshal(cpData, &cpMap)

	resp := &core.CheckpointDetailResponse{
		Checkpoint: cpMap,
	}

	if includeProof {
		proofSteps, unavailable, err := server.GenerateInclusionProof(s.storage, cp, leafIndex)
		if err != nil {
			return nil, fmt.Errorf("generate inclusion proof: %w", err)
		}
		if unavailable != "" {
			resp.ProofUnavailable = unavailable
		} else {
			proofMap := map[string]any{
				"leaf_index":  leafIndex,
				"merkle_root": cp.MerkleRoot,
				"path":        proofSteps,
			}
			resp.InclusionProof = proofMap
		}
	}

	return resp, nil
}

// CreateCheckpoint creates a new checkpoint from audit entries.
func (s *Service) CreateCheckpoint() (*core.Checkpoint, error) {
	return server.CreateCheckpoint(s.keys, s.storage, s.serviceID)
}

// ServiceID returns the service identifier.
func (s *Service) ServiceID() string {
	return s.serviceID
}

// GetHealth returns the current health status of the service.
func (s *Service) GetHealth() HealthReport {
	storageType := "sqlite"
	if strings.HasPrefix(s.storageDSN, "postgres://") || strings.HasPrefix(s.storageDSN, "postgresql://") {
		storageType = "postgres"
	}

	connected := true
	if s.storage == nil {
		connected = false
	}

	status := "healthy"
	if !connected {
		status = "unhealthy"
	}

	uptime := time.Since(s.startedAt).Truncate(time.Second).String()

	return HealthReport{
		Status: status,
		Storage: StorageHealth{
			Connected: connected,
			Type:      storageType,
		},
		Uptime:  uptime,
		Version: core.ProtocolVersion,
	}
}

// runRetentionLoop periodically deletes expired audit entries.
// Uses leader lease to prevent duplicate work across replicas.
func (s *Service) runRetentionLoop() {
	defer s.wg.Done()
	ticker := time.NewTicker(time.Duration(s.retentionIntervalSeconds) * time.Second)
	defer ticker.Stop()

	holderID := fmt.Sprintf("retention-%s-%d", s.serviceID, time.Now().UnixNano())

	for {
		select {
		case <-s.stopCh:
			s.storage.ReleaseLeader("retention", holderID)
			return
		case <-ticker.C:
			acquired, _ := s.storage.TryAcquireLeader("retention", holderID, s.retentionIntervalSeconds*2)
			if !acquired {
				continue // another instance holds the lease
			}
			now := time.Now().UTC().Format(time.RFC3339)
			_, _ = s.storage.DeleteExpiredAuditEntries(now)
		}
	}
}

// runCheckpointLoop periodically creates checkpoints from new audit entries.
// Uses leader lease to prevent duplicate work across replicas.
func (s *Service) runCheckpointLoop() {
	defer s.wg.Done()

	interval := s.checkpointPolicy.IntervalSeconds
	if interval <= 0 {
		interval = 60
	}
	minEntries := s.checkpointPolicy.MinEntries
	if minEntries <= 0 {
		minEntries = 1
	}

	holderID := fmt.Sprintf("checkpoint-%s-%d", s.serviceID, time.Now().UnixNano())

	ticker := time.NewTicker(time.Duration(interval) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-s.stopCh:
			s.storage.ReleaseLeader("checkpoint", holderID)
			return
		case <-ticker.C:
			acquired, _ := s.storage.TryAcquireLeader("checkpoint", holderID, interval*2)
			if !acquired {
				continue // another instance holds the lease
			}
			// Check if there are enough new entries.
			maxSeq, err := s.storage.GetMaxAuditSequence()
			if err != nil || maxSeq == 0 {
				continue
			}

			// Get last checkpoint to see what's already covered.
			checkpoints, err := s.storage.ListCheckpoints(100)
			if err != nil {
				continue
			}
			lastCovered := 0
			if len(checkpoints) > 0 {
				last := checkpoints[len(checkpoints)-1]
				lastCovered = last.Range["last_sequence"]
			}

			newEntries := maxSeq - lastCovered
			if newEntries < minEntries {
				continue
			}

			cp, err := s.CreateCheckpoint()
			if err != nil || cp == nil {
				continue
			}

			// Fire hook.
			if s.hooks != nil && s.hooks.OnCheckpointCreated != nil {
				callHook(func() {
					s.hooks.OnCheckpointCreated(cp.CheckpointID, cp.EntryCount)
				})
			}
		}
	}
}
