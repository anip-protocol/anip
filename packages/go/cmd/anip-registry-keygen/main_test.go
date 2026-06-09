package main

import (
	"encoding/base64"
	"os/exec"
	"strings"
	"testing"
)

func TestRegistryKeygenOutputsUsableEnv(t *testing.T) {
	cmd := exec.Command("go", "run", ".", "--key-id", "registry-test-key")
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("keygen failed: %v\n%s", err, out)
	}
	lines := strings.Split(strings.TrimSpace(string(out)), "\n")
	values := map[string]string{}
	for _, line := range lines {
		if strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if ok {
			values[key] = value
		}
	}
	if values["ANIP_REGISTRY_KEY_ID"] != "registry-test-key" {
		t.Fatalf("unexpected key id output: %q", values["ANIP_REGISTRY_KEY_ID"])
	}
	seed, err := base64.StdEncoding.DecodeString(values["ANIP_REGISTRY_ED25519_PRIVATE_KEY"])
	if err != nil {
		t.Fatalf("private key seed is not base64: %v", err)
	}
	if len(seed) != 32 {
		t.Fatalf("expected 32-byte seed, got %d", len(seed))
	}
	if !strings.HasPrefix(values["ANIP_REGISTRY_EXTRA_PUBLIC_KEYS"], "registry-test-key=") {
		t.Fatalf("unexpected public key rotation entry: %q", values["ANIP_REGISTRY_EXTRA_PUBLIC_KEYS"])
	}
}
