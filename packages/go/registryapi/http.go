package registryapi

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

type HandlerOptions struct {
	SigningMode                     string
	ActiveKeyID                     string
	PublishToken                    string
	AdminToken                      string
	LegacyGlobalPublishTokenEnabled bool
	PublisherID                     string
	PublisherType                   string
	Logger                          *slog.Logger
	Metrics                         *RegistryMetrics
	PublicBaseURL                   string
	GitHubOAuthClientID             string
	GitHubOAuthClientSecret         string
	GitHubOAuthExchange             GitHubOAuthExchangeFunc
	SessionCookieSecure             bool
	BrowserSessionTTL               time.Duration
	AdminGitHubLogins               []string
}

type PublishAuthorizer interface {
	AuthorizePublish(ctx context.Context, token string, operation string, artifactID string) (PublishAuthContext, error)
}

type PublisherSelfServiceStore interface {
	AuthenticatePublisherToken(ctx context.Context, token string) (PublishAuthContext, RegistryPublishTokenScopes, error)
	GetPublisher(ctx context.Context, publisherID string) (RegistryPublisher, bool, error)
	UpdatePublisher(ctx context.Context, publisherID string, request UpdatePublisherRequest) (RegistryPublisher, error)
	ListPublisherNamespaces(ctx context.Context, publisherID string) ([]RegistryNamespaceSummary, error)
	CreatePublisherNamespace(ctx context.Context, publisherID string, request CreateNamespaceRequest) (RegistryNamespaceSummary, error)
	ListPublisherArtifacts(ctx context.Context, publisherID string) ([]PublisherArtifactSummary, error)
	ListPublisherTokens(ctx context.Context, publisherID string) ([]RegistryPublishTokenSummary, error)
	CreatePublisherToken(ctx context.Context, publisherID string, request CreatePublishTokenRequest) (CreatePublishTokenResult, error)
	RevokePublisherToken(ctx context.Context, publisherID string, tokenID string) (RegistryPublishTokenSummary, bool, error)
}

type BrowserSessionStore interface {
	CreateOrUpdateGitHubBrowserSession(ctx context.Context, identity GitHubOAuthIdentity, ttl time.Duration) (RegistryBrowserSessionContext, string, error)
	AuthenticateBrowserSession(ctx context.Context, token string) (RegistryBrowserSessionContext, error)
	RevokeBrowserSession(ctx context.Context, token string) error
}

type NamespaceAdminStore interface {
	ListNamespaces(ctx context.Context, query RegistryAdminListQuery) (PaginatedRegistryNamespaces, error)
	ListPublishers(ctx context.Context, query RegistryAdminListQuery) (PaginatedRegistryPublishers, error)
	ListArtifactOwnership(ctx context.Context, query RegistryAdminListQuery) (PaginatedPublisherArtifacts, error)
	UpdateNamespaceStatus(ctx context.Context, namespace string, request UpdateNamespaceStatusRequest) (RegistryNamespaceSummary, bool, error)
	UpdatePublisherStatus(ctx context.Context, publisherID string, request UpdatePublisherStatusRequest) (RegistryPublisher, bool, error)
	UpdateArtifactOwnershipStatus(ctx context.Context, artifactKind string, artifactID string, request UpdateArtifactOwnershipStatusRequest) (PublisherArtifactSummary, bool, error)
	TransferArtifactOwnership(ctx context.Context, artifactKind string, artifactID string, request TransferArtifactOwnershipRequest) (PublisherArtifactSummary, bool, error)
	TransferNamespaceOwnership(ctx context.Context, namespace string, request TransferNamespaceRequest) (RegistryNamespaceSummary, bool, error)
	ListAbuseReports(ctx context.Context, query RegistryAdminListQuery) (PaginatedRegistryAbuseReports, error)
	CreateAbuseReport(ctx context.Context, request CreateAbuseReportRequest) (RegistryAbuseReport, error)
	UpdateAbuseReportStatus(ctx context.Context, reportID string, request UpdateAbuseReportStatusRequest) (RegistryAbuseReport, bool, error)
	ApplyAbuseTakedown(ctx context.Context, reportID string, request ApplyAbuseTakedownRequest) (RegistryAbuseReport, bool, error)
}

type RegistryUserAdminStore interface {
	ListRegistryUsers(ctx context.Context, query RegistryAdminListQuery) (PaginatedRegistryUsers, error)
}

func NewHandler(store Store) http.Handler {
	return NewHandlerWithOptions(store, HandlerOptions{SigningMode: "dev"})
}

func NewHandlerWithOptions(store Store, options HandlerOptions) http.Handler {
	mux := http.NewServeMux()
	signingMode := strings.TrimSpace(options.SigningMode)
	if signingMode == "" {
		signingMode = "dev"
	}
	activeKeyID := strings.TrimSpace(options.ActiveKeyID)
	if activeKeyID == "" {
		keys := store.ListPublicKeys()
		if len(keys) > 0 {
			activeKeyID = keys[0].KeyID
		}
	}
	publishToken := strings.TrimSpace(options.PublishToken)
	logger := options.Logger
	if logger == nil {
		logger = slog.Default()
	}
	metrics := options.Metrics
	if metrics == nil {
		metrics = NewRegistryMetrics()
	}
	publisherID := strings.TrimSpace(options.PublisherID)
	if publisherID == "" {
		publisherID = "studio-local"
	}
	publisherType := strings.TrimSpace(options.PublisherType)
	if publisherType == "" {
		publisherType = "studio"
	}
	publicBaseURL := strings.TrimRight(strings.TrimSpace(options.PublicBaseURL), "/")
	sessionTTL := options.BrowserSessionTTL
	if sessionTTL <= 0 {
		sessionTTL = 30 * 24 * time.Hour
	}
	adminGitHubLogins := normalizedStringSet(options.AdminGitHubLogins)

	mux.HandleFunc("GET /registry-api/v1/healthz", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"status":        "ok",
			"service":       "anip-registry",
			"signing_mode":  signingMode,
			"active_key_id": activeKeyID,
		})
	})

	mux.HandleFunc("GET /registry-api/v1/readyz", func(w http.ResponseWriter, r *http.Request) {
		status, err := readinessStatus(r.Context(), store)
		code := http.StatusOK
		readinessLabel := "ok"
		if err != nil {
			code = http.StatusServiceUnavailable
			readinessLabel = "error"
			status["error"] = err.Error()
		}
		if migration, ok := status["migration"].(MigrationStatus); ok {
			metrics.RecordReadiness(readinessLabel, migration)
		}
		writeJSON(w, code, status)
	})

	mux.HandleFunc("GET /registry-api/v1/metrics", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte(metrics.PrometheusText()))
	})

	mux.HandleFunc("GET /registry-api/v1/auth/github/start", func(w http.ResponseWriter, r *http.Request) {
		clientID := strings.TrimSpace(options.GitHubOAuthClientID)
		if clientID == "" {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "github oauth is not configured"})
			return
		}
		state, err := randomTokenSecret()
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to create oauth state"})
			return
		}
		secure := registrySecureCookie(r, options.SessionCookieSecure)
		http.SetCookie(w, oauthStateCookie(state, secure))
		if returnTo := safeRegistryReturnTo(r.URL.Query().Get("return_to")); returnTo != "" {
			http.SetCookie(w, oauthReturnToCookie(returnTo, secure))
		}
		redirectURI := registryOAuthRedirectURI(r, publicBaseURL)
		params := url.Values{}
		params.Set("client_id", clientID)
		params.Set("redirect_uri", redirectURI)
		params.Set("state", state)
		params.Set("scope", "read:user user:email")
		http.Redirect(w, r, "https://github.com/login/oauth/authorize?"+params.Encode(), http.StatusFound)
	})

	mux.HandleFunc("GET /registry-api/v1/auth/github/callback", func(w http.ResponseWriter, r *http.Request) {
		sessionStore, ok := store.(BrowserSessionStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "browser sessions are not available for this registry store"})
			return
		}
		expectedState, err := r.Cookie(registryOAuthStateCookieName)
		if err != nil || expectedState.Value == "" || r.URL.Query().Get("state") != expectedState.Value {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid github oauth state"})
			return
		}
		code := strings.TrimSpace(r.URL.Query().Get("code"))
		if code == "" {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "missing github oauth code"})
			return
		}
		secure := registrySecureCookie(r, options.SessionCookieSecure)
		redirectURI := registryOAuthRedirectURI(r, publicBaseURL)
		exchange := options.GitHubOAuthExchange
		if exchange == nil {
			exchange = defaultGitHubOAuthExchange(options.GitHubOAuthClientID, options.GitHubOAuthClientSecret, redirectURI)
		}
		identity, err := exchange(r.Context(), code)
		if err != nil {
			logger.Warn("github_oauth_exchange_failed", "error", err)
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "github oauth exchange failed"})
			return
		}
		_, sessionToken, err := sessionStore.CreateOrUpdateGitHubBrowserSession(r.Context(), identity, sessionTTL)
		if err != nil {
			logger.Warn("github_oauth_session_failed", "error", err)
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to create registry session"})
			return
		}
		returnTo := "/registry/publisher"
		if returnToCookie, err := r.Cookie(registryOAuthReturnToCookieName); err == nil {
			if safeReturnTo := safeRegistryReturnTo(returnToCookie.Value); safeReturnTo != "" {
				returnTo = safeReturnTo
			}
		}
		http.SetCookie(w, expiredCookie(registryOAuthStateCookieName, "/registry-api/v1/auth/github", secure))
		http.SetCookie(w, expiredCookie(registryOAuthReturnToCookieName, "/registry-api/v1/auth/github", secure))
		http.SetCookie(w, browserSessionCookie(sessionToken, secure, int(sessionTTL.Seconds())))
		http.Redirect(w, r, returnTo, http.StatusFound)
	})

	mux.HandleFunc("GET /registry-api/v1/auth/session", func(w http.ResponseWriter, r *http.Request) {
		sessionStore, ok := store.(BrowserSessionStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "browser sessions are not available for this registry store"})
			return
		}
		session, ok := browserSessionToken(r)
		if !ok {
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid registry browser session is required"})
			return
		}
		sessionContext, err := sessionStore.AuthenticateBrowserSession(r.Context(), session)
		if err != nil {
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid registry browser session is required"})
			return
		}
		sessionContext.Admin = browserSessionIsRegistryAdmin(sessionContext, adminGitHubLogins)
		writeJSON(w, http.StatusOK, map[string]any{"session": sessionContext})
	})

	mux.HandleFunc("POST /registry-api/v1/auth/logout", func(w http.ResponseWriter, r *http.Request) {
		sessionStore, ok := store.(BrowserSessionStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "browser sessions are not available for this registry store"})
			return
		}
		if session, ok := browserSessionToken(r); ok {
			_ = sessionStore.RevokeBrowserSession(r.Context(), session)
		}
		secure := registrySecureCookie(r, options.SessionCookieSecure)
		http.SetCookie(w, expiredCookie(registrySessionCookieName, "/", secure))
		writeJSON(w, http.StatusOK, map[string]any{"status": "logged_out"})
	})

	mux.HandleFunc("GET /registry-api/v1/publications", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"items": store.ListPublications(),
		})
	})

	mux.HandleFunc("GET /registry-api/v1/keys", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"signing_mode":  signingMode,
			"active_key_id": activeKeyID,
			"items":         store.ListPublicKeys(),
		})
	})

	mux.HandleFunc("GET /registry-api/v1/templates", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, http.StatusOK, map[string]any{
			"items": store.ListTemplates(),
		})
	})

	mux.HandleFunc("GET /registry-api/v1/me/publisher", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, scopes, ok := authenticatePublisherSelfService(w, r, store, "")
		if !ok {
			return
		}
		publisher, exists, err := selfStore.GetPublisher(r.Context(), auth.PublisherID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to load publisher"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "publisher not found"})
			return
		}
		writeJSON(w, http.StatusOK, PublisherSelfServiceContext{
			Publisher: publisher,
			Scopes:    scopes,
		})
	})

	mux.HandleFunc("PATCH /registry-api/v1/me/publisher", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "manage:publisher")
		if !ok {
			return
		}
		var request UpdatePublisherRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		publisher, err := selfStore.UpdatePublisher(r.Context(), auth.PublisherID, request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "display_name is required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to update publisher"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"publisher": publisher})
	})

	mux.HandleFunc("GET /registry-api/v1/me/namespaces", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "")
		if !ok {
			return
		}
		items, err := selfStore.ListPublisherNamespaces(r.Context(), auth.PublisherID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list publisher namespaces"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"items": items})
	})

	mux.HandleFunc("POST /registry-api/v1/me/namespaces", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "manage:publisher")
		if !ok {
			return
		}
		var request CreateNamespaceRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		namespace, err := selfStore.CreatePublisherNamespace(r.Context(), auth.PublisherID, request)
		if err != nil {
			if errors.Is(err, ErrNamespaceExists) {
				writeJSON(w, http.StatusConflict, map[string]any{"error": err.Error()})
				return
			}
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid namespace and artifact_kinds are required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to create namespace"})
			return
		}
		writeJSON(w, http.StatusCreated, map[string]any{"namespace": namespace})
	})

	mux.HandleFunc("GET /registry-api/v1/admin/namespaces", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry namespace administration is not supported by this store"})
			return
		}
		items, err := adminStore.ListNamespaces(r.Context(), parseRegistryAdminListQuery(r))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list namespaces"})
			return
		}
		writeJSON(w, http.StatusOK, items)
	})

	mux.HandleFunc("GET /registry-api/v1/admin/publishers", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry publisher administration is not supported by this store"})
			return
		}
		items, err := adminStore.ListPublishers(r.Context(), parseRegistryAdminListQuery(r))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list publishers"})
			return
		}
		writeJSON(w, http.StatusOK, items)
	})

	mux.HandleFunc("GET /registry-api/v1/admin/users", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(RegistryUserAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry user administration is not supported by this store"})
			return
		}
		items, err := adminStore.ListRegistryUsers(r.Context(), parseRegistryAdminListQuery(r))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list users"})
			return
		}
		writeJSON(w, http.StatusOK, items)
	})

	mux.HandleFunc("GET /registry-api/v1/admin/artifacts", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry artifact administration is not supported by this store"})
			return
		}
		items, err := adminStore.ListArtifactOwnership(r.Context(), parseRegistryAdminListQuery(r))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list artifacts"})
			return
		}
		writeJSON(w, http.StatusOK, items)
	})

	mux.HandleFunc("GET /registry-api/v1/admin/abuse-reports", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry abuse report administration is not supported by this store"})
			return
		}
		items, err := adminStore.ListAbuseReports(r.Context(), parseRegistryAdminListQuery(r))
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list abuse reports"})
			return
		}
		writeJSON(w, http.StatusOK, items)
	})

	mux.HandleFunc("POST /registry-api/v1/admin/abuse-reports", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry abuse report administration is not supported by this store"})
			return
		}
		var request CreateAbuseReportRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid abuse report request"})
			return
		}
		report, err := adminStore.CreateAbuseReport(r.Context(), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid target, category, and reason are required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to create abuse report"})
			return
		}
		writeJSON(w, http.StatusCreated, map[string]any{"report": report})
	})

	mux.HandleFunc("PATCH /registry-api/v1/admin/namespaces/{namespace...}", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry namespace administration is not supported by this store"})
			return
		}
		var request UpdateNamespaceStatusRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		namespace, exists, err := adminStore.UpdateNamespaceStatus(r.Context(), r.PathValue("namespace"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid namespace status is required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to update namespace"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "namespace not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"namespace": namespace})
	})

	mux.HandleFunc("POST /registry-api/v1/admin/namespace-transfer/{namespace...}", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry namespace transfer is not supported by this store"})
			return
		}
		var request TransferNamespaceRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid namespace transfer request"})
			return
		}
		namespace, exists, err := adminStore.TransferNamespaceOwnership(r.Context(), r.PathValue("namespace"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid active target publisher and transferable namespace are required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to transfer namespace"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "namespace not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"namespace": namespace})
	})

	mux.HandleFunc("PATCH /registry-api/v1/admin/publishers/{publisherID}/status", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry publisher administration is not supported by this store"})
			return
		}
		var request UpdatePublisherStatusRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		publisher, exists, err := adminStore.UpdatePublisherStatus(r.Context(), r.PathValue("publisherID"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid publisher status is required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to update publisher status"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "publisher not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"publisher": publisher})
	})

	mux.HandleFunc("PATCH /registry-api/v1/admin/artifact-status/{artifactKind}/{artifactID...}", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry artifact administration is not supported by this store"})
			return
		}
		var request UpdateArtifactOwnershipStatusRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		artifact, exists, err := adminStore.UpdateArtifactOwnershipStatus(r.Context(), r.PathValue("artifactKind"), r.PathValue("artifactID"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid artifact kind and status are required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to update artifact status"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "artifact ownership not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"artifact": artifact})
	})

	mux.HandleFunc("PATCH /registry-api/v1/admin/abuse-reports/{reportID}/status", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry abuse report administration is not supported by this store"})
			return
		}
		var request UpdateAbuseReportStatusRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid abuse report status request"})
			return
		}
		report, exists, err := adminStore.UpdateAbuseReportStatus(r.Context(), r.PathValue("reportID"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid abuse report status is required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to update abuse report"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "abuse report not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"report": report})
	})

	mux.HandleFunc("POST /registry-api/v1/admin/abuse-reports/{reportID}/takedown", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry abuse takedown is not supported by this store"})
			return
		}
		var request ApplyAbuseTakedownRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid abuse takedown request"})
			return
		}
		report, exists, err := adminStore.ApplyAbuseTakedown(r.Context(), r.PathValue("reportID"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "abuse report target cannot be suspended"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to apply abuse takedown"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "abuse report not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"report": report})
	})

	mux.HandleFunc("POST /registry-api/v1/admin/artifact-transfer/{artifactKind}/{artifactID...}", func(w http.ResponseWriter, r *http.Request) {
		if !authorizeRegistryAdminRequest(w, r, store, options.AdminToken, adminGitHubLogins) {
			return
		}
		adminStore, ok := store.(NamespaceAdminStore)
		if !ok {
			writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "registry artifact transfer is not supported by this store"})
			return
		}
		var request TransferArtifactOwnershipRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid artifact transfer request"})
			return
		}
		artifact, exists, err := adminStore.TransferArtifactOwnership(r.Context(), r.PathValue("artifactKind"), r.PathValue("artifactID"), request)
		if err != nil {
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": "valid target publisher and active target namespace are required"})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to transfer artifact ownership"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "artifact ownership not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"artifact": artifact})
	})

	mux.HandleFunc("GET /registry-api/v1/me/artifacts", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "")
		if !ok {
			return
		}
		items, err := selfStore.ListPublisherArtifacts(r.Context(), auth.PublisherID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list publisher artifacts"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"items": items})
	})

	mux.HandleFunc("GET /registry-api/v1/me/tokens", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "manage:tokens")
		if !ok {
			return
		}
		items, err := selfStore.ListPublisherTokens(r.Context(), auth.PublisherID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to list publish tokens"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"items": items})
	})

	mux.HandleFunc("POST /registry-api/v1/me/tokens", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "manage:tokens")
		if !ok {
			return
		}
		r.Body = http.MaxBytesReader(w, r.Body, MaxCreatePublishTokenRequestBytes)
		var request CreatePublishTokenRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		result, err := selfStore.CreatePublisherToken(r.Context(), auth.PublisherID, request)
		if err != nil {
			if errors.Is(err, ErrUnauthorizedPublish) {
				writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "publisher is not authorized for requested token scopes"})
				return
			}
			if errors.Is(err, ErrInvalidPackage) {
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
				return
			}
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to create publish token"})
			return
		}
		writeJSON(w, http.StatusCreated, result)
	})

	mux.HandleFunc("DELETE /registry-api/v1/me/tokens/{tokenID}", func(w http.ResponseWriter, r *http.Request) {
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "manage:tokens")
		if !ok {
			return
		}
		tokenID := r.PathValue("tokenID")
		token, exists, err := selfStore.RevokePublisherToken(r.Context(), auth.PublisherID, tokenID)
		if err != nil {
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to revoke publish token"})
			return
		}
		if !exists {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "publish token not found"})
			return
		}
		writeJSON(w, http.StatusOK, map[string]any{"token": token})
	})

	mux.HandleFunc("POST /registry-api/v1/templates", func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, MaxTemplatePublishRequestBytes)
		var request PublishTemplateRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			metrics.RecordPublish("template", "invalid_request")
			logger.Warn("registry_publish_rejected", "kind", "template", "reason", "invalid_request")
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		auth, ok := authorizePublishRequest(r.Context(), r, store, options, publishToken, publisherID, publisherType, "publish:template", request.TemplateID)
		if !ok {
			metrics.RecordPublish("template", "unauthorized")
			logger.Warn("registry_publish_rejected", "kind", "template", "template_id", request.TemplateID, "reason", "unauthorized")
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publish bearer token is required"})
			return
		}
		request.PublisherID = auth.PublisherID
		request.PublisherType = auth.PublisherType
		result, err := store.PublishTemplate(request)
		if err != nil {
			if errors.Is(err, ErrPackageVersionExists) {
				metrics.RecordPublish("template", "conflict")
				logger.Warn("registry_publish_rejected", "kind", "template", "template_id", request.TemplateID, "template_version", request.TemplateVersion, "reason", "version_exists")
				writeJSON(w, http.StatusConflict, map[string]any{"error": err.Error()})
				return
			}
			if errors.Is(err, ErrInvalidPackage) {
				metrics.RecordPublish("template", "invalid")
				logger.Warn("registry_publish_rejected", "kind", "template", "template_id", request.TemplateID, "template_version", request.TemplateVersion, "reason", err.Error())
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
				return
			}
			if errors.Is(err, ErrUnauthorizedPublish) {
				metrics.RecordPublish("template", "unauthorized")
				logger.Warn("registry_publish_rejected", "kind", "template", "template_id", request.TemplateID, "template_version", request.TemplateVersion, "reason", "unauthorized")
				writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "publisher is not authorized for this template"})
				return
			}
			metrics.RecordPublish("template", "error")
			logger.Error("registry_publish_failed", "kind", "template", "template_id", request.TemplateID, "template_version", request.TemplateVersion, "error", err.Error())
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to publish template"})
			return
		}
		metrics.RecordPublish("template", "success")
		logger.Info("registry_publish_succeeded", "kind", "template", "template_id", result.Template.TemplateID, "template_version", result.Template.TemplateVersion, "manifest_digest", result.Template.ManifestDigest, "template_digest", result.Template.TemplateDigest, "publisher_id", result.Template.PublisherID, "publisher_type", result.Template.PublisherType)
		writeJSON(w, http.StatusCreated, result)
	})

	mux.HandleFunc("POST /registry-api/v1/publications", func(w http.ResponseWriter, r *http.Request) {
		r.Body = http.MaxBytesReader(w, r.Body, MaxPublishRequestBytes)
		var request PublishPackageRequest
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			metrics.RecordPublish("package", "invalid_request")
			logger.Warn("registry_publish_rejected", "kind", "package", "reason", "invalid_request")
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "invalid request body"})
			return
		}
		if request.PackageID == "" || request.PackageVersion == "" || request.ProjectRef == "" {
			metrics.RecordPublish("package", "invalid_request")
			logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", "missing_required_identity")
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "package_id, package_version, and project_ref are required"})
			return
		}
		if request.ProductRevisionRef == "" || request.DeveloperRevisionRef == "" || request.ContractSignature == "" {
			metrics.RecordPublish("package", "invalid_request")
			logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", "missing_revision_identity")
			writeJSON(w, http.StatusBadRequest, map[string]any{"error": "product_revision_ref, developer_revision_ref, and contract_signature are required"})
			return
		}
		auth, ok := authorizePublishRequest(r.Context(), r, store, options, publishToken, publisherID, publisherType, "publish:package", request.PackageID)
		if !ok {
			metrics.RecordPublish("package", "unauthorized")
			logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", "unauthorized")
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publish bearer token is required"})
			return
		}
		request.PublisherID = auth.PublisherID
		request.PublisherType = auth.PublisherType

		result, err := store.PublishPackage(request)
		if err != nil {
			if errors.Is(err, ErrPackageVersionExists) {
				metrics.RecordPublish("package", "conflict")
				logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", "version_exists")
				writeJSON(w, http.StatusConflict, map[string]any{"error": err.Error()})
				return
			}
			if errors.Is(err, ErrInvalidPackage) {
				metrics.RecordPublish("package", "invalid")
				logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", err.Error())
				writeJSON(w, http.StatusBadRequest, map[string]any{"error": err.Error()})
				return
			}
			if errors.Is(err, ErrUnauthorizedPublish) {
				metrics.RecordPublish("package", "unauthorized")
				logger.Warn("registry_publish_rejected", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "reason", "unauthorized")
				writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "publisher is not authorized for this package"})
				return
			}
			metrics.RecordPublish("package", "error")
			logger.Error("registry_publish_failed", "kind", "package", "package_id", request.PackageID, "package_version", request.PackageVersion, "error", err.Error())
			writeJSON(w, http.StatusInternalServerError, map[string]any{"error": "failed to publish package"})
			return
		}
		metrics.RecordPublish("package", "success")
		logger.Info("registry_publish_succeeded", "kind", "package", "package_id", result.Package.PackageID, "package_version", result.Package.PackageVersion, "manifest_digest", result.Package.ManifestDigest, "definition_digest", result.Package.DefinitionDigest, "receipt_id", result.Receipt.ReceiptID, "key_id", result.Receipt.KeyID, "publisher_id", result.Package.PublisherID, "publisher_type", result.Package.PublisherType)
		writeJSON(w, http.StatusCreated, result)
	})

	mux.HandleFunc("GET /registry-api/v1/templates/{templateID}/{version}", func(w http.ResponseWriter, r *http.Request) {
		templateID := r.PathValue("templateID")
		version := r.PathValue("version")
		record, ok := store.GetTemplate(templateID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "template version not found"})
			return
		}
		writeJSON(w, http.StatusOK, record)
	})

	mux.HandleFunc("GET /registry-api/v1/templates/{templateID}/{version}/download", func(w http.ResponseWriter, r *http.Request) {
		templateID := r.PathValue("templateID")
		version := r.PathValue("version")
		record, ok := store.RecordTemplateDownload(templateID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "template version not found"})
			return
		}
		metrics.RecordDownload("template")
		logger.Info("registry_download", "kind", "template", "template_id", templateID, "template_version", version, "download_count", record.DownloadCount)
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s-%s.anip-template.json"`, sanitizeDownloadFilename(templateID), sanitizeDownloadFilename(version)))
		writeJSON(w, http.StatusOK, record.Package)
	})

	mux.HandleFunc("GET /registry-api/v1/packages/{packageID}/{version}", func(w http.ResponseWriter, r *http.Request) {
		packageID := r.PathValue("packageID")
		version := r.PathValue("version")
		record, ok := store.GetPackage(packageID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "package version not found"})
			return
		}
		writeJSON(w, http.StatusOK, record)
	})

	mux.HandleFunc("GET /registry-api/v1/packages/{packageID}/{version}/download", func(w http.ResponseWriter, r *http.Request) {
		packageID := r.PathValue("packageID")
		version := r.PathValue("version")
		record, ok := store.RecordPackageDownload(packageID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "package version not found"})
			return
		}
		metrics.RecordDownload("package")
		logger.Info("registry_download", "kind", "package", "package_id", packageID, "package_version", version, "download_count", record.DownloadCount)
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s-%s.anip-package.json"`, sanitizeDownloadFilename(packageID), sanitizeDownloadFilename(version)))
		writeJSON(w, http.StatusOK, record)
	})

	mux.HandleFunc("GET /registry-api/v1/packages/{packageID}/{version}/lock", func(w http.ResponseWriter, r *http.Request) {
		packageID := r.PathValue("packageID")
		version := r.PathValue("version")
		record, ok := store.GetPackage(packageID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "package version not found"})
			return
		}
		receipt, ok := store.GetReceipt(packageID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "package receipt not found"})
			return
		}
		lock := RegistryPackageLock{
			LockSchemaVersion:         "anip-package-lock/v1",
			ArtifactType:              "anip_package_lock",
			SourceKind:                "registry",
			RegistryURL:               requestRegistryAPIBase(r),
			PackageID:                 record.PackageID,
			PackageVersion:            record.PackageVersion,
			ContractSignature:         record.ContractSignature,
			SchemaVersion:             record.SchemaVersion,
			DefinitionDigest:          record.DefinitionDigest,
			ManifestDigest:            record.ManifestDigest,
			LockDigest:                record.LockDigest,
			PackageExecutionSignature: record.PackageExecutionSignature,
			ReceiptSignature:          receipt.RegistrySignature,
			ReceiptAuthority:          "remote-registry",
			ReceiptKeyID:              receipt.KeyID,
			ReceiptAlgorithm:          receipt.SignatureAlgorithm,
			ReceiptIssuedAt:           receipt.IssuedAt,
			RegistrySigningMode:       signingMode,
			RegistryActiveKeyID:       activeKeyID,
			PublisherID:               record.PublisherID,
			PublisherType:             record.PublisherType,
		}
		w.Header().Set("Content-Disposition", fmt.Sprintf(`attachment; filename="%s-%s.anip.lock.json"`, sanitizeDownloadFilename(packageID), sanitizeDownloadFilename(version)))
		writeJSON(w, http.StatusOK, lock)
	})

	mux.HandleFunc("GET /registry-api/v1/packages/{packageID}/{version}/receipt", func(w http.ResponseWriter, r *http.Request) {
		packageID := r.PathValue("packageID")
		version := r.PathValue("version")
		record, ok := store.GetReceipt(packageID, version)
		if !ok {
			writeJSON(w, http.StatusNotFound, map[string]any{"error": "package receipt not found"})
			return
		}
		writeJSON(w, http.StatusOK, record)
	})

	return withRequestObservability(withCORS(mux), logger, metrics)
}

func readinessStatus(ctx context.Context, store Store) (map[string]any, error) {
	status := map[string]any{
		"status":  "ok",
		"service": "anip-registry",
	}
	readyStore, ok := store.(ReadyStore)
	if !ok {
		status["migration"] = MigrationStatus{Applied: true}
		return status, nil
	}
	migration, migrationErr := readyStore.MigrationStatus(ctx)
	status["migration"] = migration
	if migrationErr != nil {
		status["status"] = "error"
		return status, migrationErr
	}
	if err := readyStore.CheckReady(ctx); err != nil {
		status["status"] = "error"
		return status, err
	}
	return status, nil
}

func requestRegistryAPIBase(r *http.Request) string {
	proto := strings.TrimSpace(r.Header.Get("X-Forwarded-Proto"))
	if proto == "" {
		if r.TLS != nil {
			proto = "https"
		} else {
			proto = "http"
		}
	}
	host := strings.TrimSpace(r.Header.Get("X-Forwarded-Host"))
	if host == "" {
		host = strings.TrimSpace(r.Host)
	}
	if host == "" {
		return ""
	}
	return fmt.Sprintf("%s://%s/registry-api/v1", proto, host)
}

func sanitizeDownloadFilename(value string) string {
	value = strings.TrimSpace(value)
	if value == "" {
		return "package"
	}
	var builder strings.Builder
	for _, r := range value {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '.' || r == '-' || r == '_' {
			builder.WriteRune(r)
		} else {
			builder.WriteByte('-')
		}
	}
	return builder.String()
}

func authorizePublishRequest(ctx context.Context, r *http.Request, store Store, options HandlerOptions, legacyToken string, legacyPublisherID string, legacyPublisherType string, operation string, artifactID string) (PublishAuthContext, bool) {
	token, ok := bearerToken(r)
	if !ok {
		return PublishAuthContext{}, false
	}
	if authorizer, ok := store.(PublishAuthorizer); ok {
		auth, err := authorizer.AuthorizePublish(ctx, token, operation, artifactID)
		if err == nil {
			return auth, true
		}
	}
	if options.LegacyGlobalPublishTokenEnabled && authorizedLegacyPublishToken(token, legacyToken) {
		return PublishAuthContext{
			PublisherID:   legacyPublisherID,
			PublisherType: legacyPublisherType,
		}, true
	}
	return PublishAuthContext{}, false
}

func authenticatePublisherSelfService(w http.ResponseWriter, r *http.Request, store Store, requiredOperation string) (PublisherSelfServiceStore, PublishAuthContext, RegistryPublishTokenScopes, bool) {
	selfStore, ok := store.(PublisherSelfServiceStore)
	if !ok {
		writeJSON(w, http.StatusNotImplemented, map[string]any{"error": "publisher self-service is not available for this registry store"})
		return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
	}
	token, ok := bearerToken(r)
	if !ok {
		sessionStore, sessionOK := store.(BrowserSessionStore)
		sessionToken, cookieOK := browserSessionToken(r)
		if !sessionOK || !cookieOK {
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publisher bearer token or browser session is required"})
			return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
		}
		sessionContext, err := sessionStore.AuthenticateBrowserSession(r.Context(), sessionToken)
		if err != nil || sessionContext.Publisher == nil {
			writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publisher bearer token or browser session is required"})
			return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
		}
		requiredOperation = strings.TrimSpace(requiredOperation)
		if requiredOperation != "" && !stringInSet(requiredOperation, sessionContext.Scopes.Operations) {
			writeJSON(w, http.StatusForbidden, map[string]any{"error": "browser session does not include required publisher management scope"})
			return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
		}
		return selfStore, PublishAuthContext{
			PublisherID:   sessionContext.Publisher.PublisherID,
			PublisherType: sessionContext.Publisher.PublisherType,
		}, sessionContext.Scopes, true
	}
	auth, scopes, err := selfStore.AuthenticatePublisherToken(r.Context(), token)
	if err != nil {
		writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publisher bearer token is required"})
		return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
	}
	requiredOperation = strings.TrimSpace(requiredOperation)
	if requiredOperation != "" && !stringInSet(requiredOperation, scopes.Operations) {
		writeJSON(w, http.StatusForbidden, map[string]any{"error": "publisher token does not include required management scope"})
		return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
	}
	return selfStore, auth, scopes, true
}

func browserSessionToken(r *http.Request) (string, bool) {
	cookie, err := r.Cookie(registrySessionCookieName)
	if err != nil {
		return "", false
	}
	token := strings.TrimSpace(cookie.Value)
	return token, token != ""
}

func bearerToken(r *http.Request) (string, bool) {
	header := strings.TrimSpace(r.Header.Get("Authorization"))
	const prefix = "Bearer "
	if !strings.HasPrefix(header, prefix) {
		return "", false
	}
	token := strings.TrimSpace(strings.TrimPrefix(header, prefix))
	return token, token != ""
}

func registrySecureCookie(r *http.Request, configured bool) bool {
	if configured || r.TLS != nil {
		return true
	}
	return strings.EqualFold(r.Header.Get("X-Forwarded-Proto"), "https")
}

func registryOAuthRedirectURI(r *http.Request, publicBaseURL string) string {
	if publicBaseURL == "" {
		scheme := "http"
		if r.TLS != nil || strings.EqualFold(r.Header.Get("X-Forwarded-Proto"), "https") {
			scheme = "https"
		}
		host := r.Host
		if forwardedHost := strings.TrimSpace(r.Header.Get("X-Forwarded-Host")); forwardedHost != "" {
			host = forwardedHost
		}
		publicBaseURL = scheme + "://" + host
	}
	return strings.TrimRight(publicBaseURL, "/") + "/registry-api/v1/auth/github/callback"
}

func authorizedLegacyPublishToken(token string, configuredToken string) bool {
	if configuredToken == "" {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(token), []byte(configuredToken)) == 1
}

func authorizeRegistryAdminRequest(w http.ResponseWriter, r *http.Request, store Store, configuredToken string, adminGitHubLogins map[string]bool) bool {
	configuredToken = strings.TrimSpace(configuredToken)
	token := strings.TrimSpace(strings.TrimPrefix(r.Header.Get("Authorization"), "Bearer "))
	if configuredToken != "" && token != "" && subtle.ConstantTimeCompare([]byte(token), []byte(configuredToken)) == 1 {
		return true
	}
	sessionStore, sessionStoreOK := store.(BrowserSessionStore)
	sessionToken, sessionTokenOK := browserSessionToken(r)
	if sessionStoreOK && sessionTokenOK {
		sessionContext, err := sessionStore.AuthenticateBrowserSession(r.Context(), sessionToken)
		if err == nil && browserSessionIsRegistryAdmin(sessionContext, adminGitHubLogins) {
			return true
		}
	}
	if len(adminGitHubLogins) == 0 && configuredToken == "" {
		writeJSON(w, http.StatusForbidden, map[string]any{"error": "registry admin auth is not configured"})
		return false
	}
	writeJSON(w, http.StatusForbidden, map[string]any{"error": "valid registry admin session or bearer token is required"})
	return false
}

func browserSessionIsRegistryAdmin(sessionContext RegistryBrowserSessionContext, adminGitHubLogins map[string]bool) bool {
	login := strings.ToLower(strings.TrimSpace(sessionContext.User.GitHubLogin))
	return login != "" && adminGitHubLogins[login]
}

func normalizedStringSet(values []string) map[string]bool {
	result := map[string]bool{}
	for _, value := range values {
		value = strings.ToLower(strings.TrimSpace(value))
		if value != "" {
			result[value] = true
		}
	}
	return result
}

func parseRegistryAdminListQuery(r *http.Request) RegistryAdminListQuery {
	query := r.URL.Query()
	limit, _ := strconv.Atoi(strings.TrimSpace(query.Get("limit")))
	offset, _ := strconv.Atoi(strings.TrimSpace(query.Get("offset")))
	if limit <= 0 {
		limit = 25
	}
	if limit > 100 {
		limit = 100
	}
	if offset < 0 {
		offset = 0
	}
	return RegistryAdminListQuery{
		Search: strings.TrimSpace(query.Get("search")),
		Status: strings.TrimSpace(query.Get("status")),
		Limit:  limit,
		Offset: offset,
	}
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		origin := strings.TrimSpace(r.Header.Get("Origin"))
		if localDevelopmentOrigin(origin) {
			w.Header().Set("Access-Control-Allow-Origin", origin)
			w.Header().Set("Access-Control-Allow-Credentials", "true")
			w.Header().Set("Vary", "Origin")
		} else {
			w.Header().Set("Access-Control-Allow-Origin", "*")
		}
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func localDevelopmentOrigin(origin string) bool {
	origin = strings.TrimSpace(origin)
	return strings.HasPrefix(origin, "http://localhost:") ||
		strings.HasPrefix(origin, "http://127.0.0.1:") ||
		strings.HasPrefix(origin, "http://[::1]:")
}

type responseRecorder struct {
	http.ResponseWriter
	status int
}

func (r *responseRecorder) WriteHeader(status int) {
	r.status = status
	r.ResponseWriter.WriteHeader(status)
}

func withRequestObservability(next http.Handler, logger *slog.Logger, metrics *RegistryMetrics) http.Handler {
	if logger == nil {
		logger = slog.Default()
	}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		start := time.Now()
		recorder := &responseRecorder{ResponseWriter: w, status: http.StatusOK}
		next.ServeHTTP(recorder, r)
		route := r.Pattern
		if route == "" {
			route = r.URL.Path
		}
		duration := time.Since(start)
		metrics.RecordRequest(r.Method, route, recorder.status, duration)
		logger.Info("registry_http_request", "method", r.Method, "route", route, "status", recorder.status, "duration_ms", duration.Milliseconds())
	})
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}
