package registryapi

import (
	"context"
	"crypto/subtle"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"
)

type HandlerOptions struct {
	SigningMode                     string
	ActiveKeyID                     string
	PublishToken                    string
	LegacyGlobalPublishTokenEnabled bool
	PublisherID                     string
	PublisherType                   string
	Logger                          *slog.Logger
	Metrics                         *RegistryMetrics
}

type PublishAuthorizer interface {
	AuthorizePublish(ctx context.Context, token string, operation string, artifactID string) (PublishAuthContext, error)
}

type PublisherSelfServiceStore interface {
	AuthenticatePublisherToken(ctx context.Context, token string) (PublishAuthContext, RegistryPublishTokenScopes, error)
	GetPublisher(ctx context.Context, publisherID string) (RegistryPublisher, bool, error)
	ListPublisherArtifacts(ctx context.Context, publisherID string) ([]PublisherArtifactSummary, error)
	ListPublisherTokens(ctx context.Context, publisherID string) ([]RegistryPublishTokenSummary, error)
	CreatePublisherToken(ctx context.Context, publisherID string, request CreatePublishTokenRequest) (CreatePublishTokenResult, error)
	RevokePublisherToken(ctx context.Context, publisherID string, tokenID string) (RegistryPublishTokenSummary, bool, error)
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
		selfStore, auth, _, ok := authenticatePublisherSelfService(w, r, store, "")
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
		writeJSON(w, http.StatusOK, map[string]any{"publisher": publisher})
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
			LockSchemaVersion:   "anip-package-lock/v1",
			ArtifactType:        "anip_package_lock",
			SourceKind:          "registry",
			RegistryURL:         requestRegistryAPIBase(r),
			PackageID:           record.PackageID,
			PackageVersion:      record.PackageVersion,
			ContractSignature:   record.ContractSignature,
			SchemaVersion:       record.SchemaVersion,
			DefinitionDigest:    record.DefinitionDigest,
			ManifestDigest:      record.ManifestDigest,
			LockDigest:          record.LockDigest,
			ReceiptSignature:    receipt.RegistrySignature,
			ReceiptAuthority:    "remote-registry",
			ReceiptKeyID:        receipt.KeyID,
			ReceiptAlgorithm:    receipt.SignatureAlgorithm,
			ReceiptIssuedAt:     receipt.IssuedAt,
			RegistrySigningMode: signingMode,
			RegistryActiveKeyID: activeKeyID,
			PublisherID:         record.PublisherID,
			PublisherType:       record.PublisherType,
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
		writeJSON(w, http.StatusUnauthorized, map[string]any{"error": "valid scoped publisher bearer token is required"})
		return nil, PublishAuthContext{}, RegistryPublishTokenScopes{}, false
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

func bearerToken(r *http.Request) (string, bool) {
	header := strings.TrimSpace(r.Header.Get("Authorization"))
	const prefix = "Bearer "
	if !strings.HasPrefix(header, prefix) {
		return "", false
	}
	token := strings.TrimSpace(strings.TrimPrefix(header, prefix))
	return token, token != ""
}

func authorizedLegacyPublishToken(token string, configuredToken string) bool {
	if configuredToken == "" {
		return false
	}
	return subtle.ConstantTimeCompare([]byte(token), []byte(configuredToken)) == 1
}

func withCORS(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
		w.Header().Set("Access-Control-Allow-Headers", "Authorization, Content-Type")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
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
