package main

import (
	"context"
	"fmt"
	"log"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strings"

	"github.com/anip-protocol/anip/packages/go/registryapi"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{}))
	slog.SetDefault(logger)

	addr := os.Getenv("ANIP_REGISTRY_ADDR")
	if addr == "" {
		addr = ":8200"
	}

	dsn := os.Getenv("ANIP_REGISTRY_DATABASE_URL")
	if dsn == "" {
		log.Fatal("ANIP_REGISTRY_DATABASE_URL is required")
	}

	signingConfig, err := resolveRegistrySigningConfig(
		os.Getenv("ANIP_REGISTRY_MODE"),
		os.Getenv("ANIP_REGISTRY_KEY_ID"),
		os.Getenv("ANIP_REGISTRY_ED25519_PRIVATE_KEY"),
	)
	if err != nil {
		log.Fatal(err)
	}
	signer := signingConfig.Signer
	if signingConfig.UsesDevKey {
		logger.Warn("registry_signing_mode", "mode", signingConfig.Mode, "key_id", signer.KeyID, "dev_key", true, "message", "set ANIP_REGISTRY_MODE=production plus ANIP_REGISTRY_ED25519_PRIVATE_KEY for production")
	} else {
		logger.Info("registry_signing_mode", "mode", signingConfig.Mode, "key_id", signer.KeyID, "dev_key", false)
	}
	legacyGlobalPublishEnabled := envBoolDefault("ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED", false)
	if strings.TrimSpace(os.Getenv("ANIP_REGISTRY_PUBLISH_TOKEN")) == "" {
		logger.Warn("registry_publish_disabled", "reason", "missing_publish_token")
	} else if legacyGlobalPublishEnabled {
		logger.Warn("registry_legacy_global_publish_token_enabled", "message", "ANIP_REGISTRY_PUBLISH_TOKEN is accepted only for transition; use scoped registry publish tokens for public publishing")
	} else {
		logger.Info("registry_legacy_global_publish_token_disabled", "message", "ANIP_REGISTRY_PUBLISH_TOKEN is configured but ignored because ANIP_REGISTRY_LEGACY_GLOBAL_PUBLISH_TOKEN_ENABLED is not true")
	}

	extraPublicKeys, err := registryapi.ParseRegistryPublicKeyList(os.Getenv("ANIP_REGISTRY_EXTRA_PUBLIC_KEYS"))
	if err != nil {
		log.Fatalf("parse ANIP_REGISTRY_EXTRA_PUBLIC_KEYS: %v", err)
	}

	runMigrations := envBoolDefault("ANIP_REGISTRY_RUN_MIGRATIONS", true)
	if envBoolDefault("ANIP_REGISTRY_MIGRATE_ONLY", false) {
		runMigrations = true
	}
	store, err := registryapi.NewPostgresStoreWithOptions(dsn, registryapi.PostgresStoreOptions{
		Signer:          signer,
		ExtraPublicKeys: extraPublicKeys,
		RunMigrations:   runMigrations,
	})
	if err != nil {
		log.Fatalf("initialize registry store: %v", err)
	}
	defer store.Close()

	if envBoolDefault("ANIP_REGISTRY_MIGRATE_ONLY", false) {
		status, err := store.MigrationStatus(context.Background())
		if err != nil {
			log.Fatalf("migration status: %v", err)
		}
		logger.Info("registry_migrate_only_complete", "applied", status.Applied, "applied_count", status.AppliedCount, "expected_count", status.ExpectedCount, "pending", status.Pending)
		return
	}

	if envBoolDefault("ANIP_REGISTRY_BOOTSTRAP_OFFICIAL_ANIP_PUBLISHER", false) {
		legacyPublisherIDs := envCSVDefault(
			"ANIP_REGISTRY_OFFICIAL_ANIP_LEGACY_PUBLISHER_IDS",
			[]string{"anip", "studio-local", "studio-dev", "local-registry", "local-dev-registry", "local-dev"},
		)
		if err := store.BootstrapOfficialANIPPublisher(context.Background(), legacyPublisherIDs); err != nil {
			log.Fatalf("bootstrap official ANIP publisher: %v", err)
		}
		logger.Info("registry_official_anip_publisher_bootstrapped", "legacy_publisher_ids", legacyPublisherIDs)
	}

	if os.Getenv("ANIP_REGISTRY_SEED_DEMO") == "1" {
		if err := store.SeedDemoData(); err != nil {
			log.Fatalf("seed demo data: %v", err)
		}
	}

	mux := http.NewServeMux()
	mux.Handle("/", registryRootHandler())
	mux.Handle("/registry-api/", registryapi.NewHandlerWithOptions(store, registryapi.HandlerOptions{
		SigningMode:                     signingConfig.Mode,
		ActiveKeyID:                     signer.KeyID,
		PublishToken:                    os.Getenv("ANIP_REGISTRY_PUBLISH_TOKEN"),
		AdminToken:                      os.Getenv("ANIP_REGISTRY_ADMIN_TOKEN"),
		LegacyGlobalPublishTokenEnabled: legacyGlobalPublishEnabled,
		PublisherID:                     firstNonEmpty(os.Getenv("ANIP_REGISTRY_PUBLISHER_ID"), "studio-local"),
		PublisherType:                   firstNonEmpty(os.Getenv("ANIP_REGISTRY_PUBLISHER_TYPE"), "studio"),
		PublicBaseURL:                   os.Getenv("ANIP_REGISTRY_PUBLIC_BASE_URL"),
		GitHubOAuthClientID:             os.Getenv("ANIP_REGISTRY_GITHUB_CLIENT_ID"),
		GitHubOAuthClientSecret:         os.Getenv("ANIP_REGISTRY_GITHUB_CLIENT_SECRET"),
		SessionCookieSecure:             envBoolDefault("ANIP_REGISTRY_SESSION_COOKIE_SECURE", false),
		Logger:                          logger,
	}))
	if uiDir := resolveRegistryUIDir(); uiDir != "" {
		logger.Info("registry_ui_enabled", "path", uiDir, "route", "/registry")
		mux.Handle("/registry", registryUIHandler(uiDir))
		mux.Handle("/registry/", registryUIHandler(uiDir))
	} else {
		logger.Warn("registry_ui_disabled", "reason", "missing_ui_dir")
	}

	logger.Info("registry_listening", "addr", addr, "run_migrations", runMigrations)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}

func envBoolDefault(name string, fallback bool) bool {
	value := strings.ToLower(strings.TrimSpace(os.Getenv(name)))
	if value == "" {
		return fallback
	}
	switch value {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}

func envCSVDefault(name string, fallback []string) []string {
	value := strings.TrimSpace(os.Getenv(name))
	if value == "" {
		return fallback
	}
	parts := strings.Split(value, ",")
	result := make([]string, 0, len(parts))
	for _, part := range parts {
		part = strings.TrimSpace(part)
		if part != "" {
			result = append(result, part)
		}
	}
	if len(result) == 0 {
		return fallback
	}
	return result
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if trimmed := strings.TrimSpace(value); trimmed != "" {
			return trimmed
		}
	}
	return ""
}

type registrySigningConfig struct {
	Mode       string
	Signer     *registryapi.RegistrySigner
	UsesDevKey bool
}

func resolveRegistrySigningConfig(modeValue string, keyID string, encodedKey string) (registrySigningConfig, error) {
	mode := strings.ToLower(strings.TrimSpace(modeValue))
	if mode == "" {
		mode = "dev"
	}
	if mode != "dev" && mode != "production" {
		return registrySigningConfig{}, fmt.Errorf("ANIP_REGISTRY_MODE must be dev or production")
	}

	keyID = strings.TrimSpace(keyID)
	encodedKey = strings.TrimSpace(encodedKey)
	if encodedKey == "" {
		if mode == "production" {
			return registrySigningConfig{}, fmt.Errorf("ANIP_REGISTRY_ED25519_PRIVATE_KEY is required when ANIP_REGISTRY_MODE=production")
		}
		return registrySigningConfig{
			Mode:       mode,
			Signer:     registryapi.NewDevRegistrySigner(),
			UsesDevKey: true,
		}, nil
	}
	if keyID == "" {
		return registrySigningConfig{}, fmt.Errorf("ANIP_REGISTRY_KEY_ID is required when ANIP_REGISTRY_ED25519_PRIVATE_KEY is set")
	}
	signer, err := registryapi.NewRegistrySignerFromBase64(keyID, encodedKey)
	if err != nil {
		return registrySigningConfig{}, fmt.Errorf("initialize registry signer: %w", err)
	}
	return registrySigningConfig{
		Mode:       mode,
		Signer:     signer,
		UsesDevKey: false,
	}, nil
}

func resolveRegistryUIDir() string {
	if configured := strings.TrimSpace(os.Getenv("ANIP_REGISTRY_UI_DIR")); configured != "" {
		if isDirectory(configured) {
			return configured
		}
		log.Printf("ANIP_REGISTRY_UI_DIR %q does not exist or is not a directory", configured)
		return ""
	}

	candidates := []string{
		filepath.Join("registry", "dist"),
		filepath.Join("..", "..", "registry", "dist"),
		filepath.Join("..", "..", "..", "registry", "dist"),
		filepath.Join("..", "..", "..", "..", "registry", "dist"),
	}
	for _, candidate := range candidates {
		abs, err := filepath.Abs(candidate)
		if err != nil {
			continue
		}
		if isDirectory(abs) {
			return abs
		}
	}
	return ""
}

func isDirectory(path string) bool {
	info, err := os.Stat(path)
	return err == nil && info.IsDir()
}

func registryRootHandler() http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/" {
			http.NotFound(w, r)
			return
		}
		http.Redirect(w, r, "/registry", http.StatusMovedPermanently)
	})
}

func registryUIHandler(uiDir string) http.Handler {
	fileServer := http.StripPrefix("/registry/", http.FileServer(http.Dir(uiDir)))
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/registry" {
			http.Redirect(w, r, "/registry/packages", http.StatusMovedPermanently)
			return
		}
		if !strings.HasPrefix(r.URL.Path, "/registry/") {
			http.NotFound(w, r)
			return
		}

		relative := strings.TrimPrefix(r.URL.Path, "/registry/")
		if relative == "" {
			http.Redirect(w, r, "/registry/packages", http.StatusMovedPermanently)
			return
		}

		cleaned := filepath.Clean(filepath.FromSlash(relative))
		if cleaned == "." || strings.HasPrefix(cleaned, "..") {
			http.NotFound(w, r)
			return
		}
		if info, err := os.Stat(filepath.Join(uiDir, cleaned)); err == nil && !info.IsDir() {
			fileServer.ServeHTTP(w, r)
			return
		}

		serveRegistryIndex(w, r, uiDir)
	})
}

func serveRegistryIndex(w http.ResponseWriter, r *http.Request, uiDir string) {
	http.ServeFile(w, r, filepath.Join(uiDir, "index.html"))
}
