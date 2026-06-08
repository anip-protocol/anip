package main

import (
	"encoding/base64"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/anip-protocol/anip/packages/go/registryapi"
)

func TestResolveRegistrySigningConfigDefaultsToDevKey(t *testing.T) {
	config, err := resolveRegistrySigningConfig("", "", "")
	if err != nil {
		t.Fatalf("resolve signing config: %v", err)
	}
	if config.Mode != "dev" || !config.UsesDevKey {
		t.Fatalf("expected dev signing mode with dev key, got %+v", config)
	}
	if config.Signer == nil || config.Signer.KeyID == "" {
		t.Fatalf("expected signer, got %+v", config.Signer)
	}
}

func TestResolveRegistrySigningConfigRequiresProductionKey(t *testing.T) {
	_, err := resolveRegistrySigningConfig("production", "", "")
	if err == nil || !strings.Contains(err.Error(), "ANIP_REGISTRY_ED25519_PRIVATE_KEY") {
		t.Fatalf("expected production key error, got %v", err)
	}
}

func TestResolveRegistrySigningConfigRequiresKeyIDWithConfiguredKey(t *testing.T) {
	encodedKey := base64.StdEncoding.EncodeToString(registryapi.NewDevRegistrySigner().PrivateKey)
	_, err := resolveRegistrySigningConfig("dev", "", encodedKey)
	if err == nil || !strings.Contains(err.Error(), "ANIP_REGISTRY_KEY_ID") {
		t.Fatalf("expected key id error, got %v", err)
	}
}

func TestResolveRegistrySigningConfigAcceptsProductionKey(t *testing.T) {
	encodedKey := base64.StdEncoding.EncodeToString(registryapi.NewDevRegistrySigner().PrivateKey)
	config, err := resolveRegistrySigningConfig("production", "registry-prod-2026-04", encodedKey)
	if err != nil {
		t.Fatalf("resolve signing config: %v", err)
	}
	if config.Mode != "production" || config.UsesDevKey {
		t.Fatalf("expected production signing mode with configured key, got %+v", config)
	}
	if config.Signer.KeyID != "registry-prod-2026-04" {
		t.Fatalf("unexpected key id %q", config.Signer.KeyID)
	}
}

func TestResolveRegistrySigningConfigRejectsUnknownMode(t *testing.T) {
	_, err := resolveRegistrySigningConfig("staging", "", "")
	if err == nil || !strings.Contains(err.Error(), "dev or production") {
		t.Fatalf("expected mode error, got %v", err)
	}
}

func TestEnvBoolDefault(t *testing.T) {
	t.Setenv("ANIP_TEST_BOOL", "true")
	if !envBoolDefault("ANIP_TEST_BOOL", false) {
		t.Fatal("expected true env value")
	}
	t.Setenv("ANIP_TEST_BOOL", "0")
	if envBoolDefault("ANIP_TEST_BOOL", true) {
		t.Fatal("expected false env value")
	}
	t.Setenv("ANIP_TEST_BOOL", "not-a-bool")
	if !envBoolDefault("ANIP_TEST_BOOL", true) {
		t.Fatal("expected fallback value")
	}
	t.Setenv("ANIP_TEST_BOOL", "")
	if envBoolDefault("ANIP_TEST_BOOL", false) {
		t.Fatal("expected empty env fallback")
	}
}

func TestRegistryRootHandlerRedirectsToRegistry(t *testing.T) {
	handler := registryRootHandler()

	recorder := httptest.NewRecorder()
	handler.ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, "/", nil))
	if recorder.Code != http.StatusMovedPermanently || recorder.Header().Get("Location") != "/registry" {
		t.Fatalf("expected registry redirect, code=%d location=%s", recorder.Code, recorder.Header().Get("Location"))
	}

	notFoundRecorder := httptest.NewRecorder()
	handler.ServeHTTP(notFoundRecorder, httptest.NewRequest(http.MethodGet, "/missing", nil))
	if notFoundRecorder.Code != http.StatusNotFound {
		t.Fatalf("expected not found for non-root path, code=%d", notFoundRecorder.Code)
	}
}

func TestRegistryUIHandlerServesIndexAndAssets(t *testing.T) {
	uiDir := t.TempDir()
	if err := os.WriteFile(filepath.Join(uiDir, "index.html"), []byte(`<html><body>registry ui</body></html>`), 0o600); err != nil {
		t.Fatalf("write index: %v", err)
	}
	assetsDir := filepath.Join(uiDir, "assets")
	if err := os.Mkdir(assetsDir, 0o700); err != nil {
		t.Fatalf("mkdir assets: %v", err)
	}
	if err := os.WriteFile(filepath.Join(assetsDir, "app.js"), []byte(`console.log("registry")`), 0o600); err != nil {
		t.Fatalf("write asset: %v", err)
	}

	handler := registryUIHandler(uiDir)

	indexRecorder := httptest.NewRecorder()
	handler.ServeHTTP(indexRecorder, httptest.NewRequest(http.MethodGet, "/registry/", nil))
	if indexRecorder.Code != http.StatusMovedPermanently || indexRecorder.Header().Get("Location") != "/registry/packages" {
		t.Fatalf("expected packages redirect, code=%d location=%s", indexRecorder.Code, indexRecorder.Header().Get("Location"))
	}

	assetRecorder := httptest.NewRecorder()
	handler.ServeHTTP(assetRecorder, httptest.NewRequest(http.MethodGet, "/registry/assets/app.js", nil))
	if assetRecorder.Code != http.StatusOK || !strings.Contains(assetRecorder.Body.String(), "registry") {
		t.Fatalf("expected asset response, code=%d body=%s", assetRecorder.Code, assetRecorder.Body.String())
	}

	spaRecorder := httptest.NewRecorder()
	handler.ServeHTTP(spaRecorder, httptest.NewRequest(http.MethodGet, "/registry/packages/example/0.1.0", nil))
	if spaRecorder.Code != http.StatusOK || !strings.Contains(spaRecorder.Body.String(), "registry ui") {
		t.Fatalf("expected SPA fallback response, code=%d body=%s", spaRecorder.Code, spaRecorder.Body.String())
	}
}
