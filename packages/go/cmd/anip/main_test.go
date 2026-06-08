package main

import (
	"bytes"
	"strings"
	"testing"
)

func TestUnifiedCLIPrintsVersion(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	code := run([]string{"version"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected version exit 0, got %d; stderr=%s", code, stderr.String())
	}
	if strings.TrimSpace(stdout.String()) != "anip CLI 0.8.0\nANIP spec anip/0.24" {
		t.Fatalf("unexpected version output: %q", stdout.String())
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
}

func TestUnifiedCLIHandlesVersionFlag(t *testing.T) {
	var stdout bytes.Buffer
	var stderr bytes.Buffer

	code := run([]string{"--version"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected --version exit 0, got %d; stderr=%s", code, stderr.String())
	}
	if strings.TrimSpace(stdout.String()) != "anip CLI 0.8.0\nANIP spec anip/0.24" {
		t.Fatalf("unexpected --version output: %q", stdout.String())
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr, got %q", stderr.String())
	}
}

func TestUnifiedCLIHandlesHelpAndUnknownCommand(t *testing.T) {
	var helpOut bytes.Buffer
	if code := run([]string{"--help"}, &helpOut, &bytes.Buffer{}); code != 0 {
		t.Fatalf("expected help exit 0, got %d", code)
	}
	if !strings.Contains(helpOut.String(), "anip generate [flags]") {
		t.Fatalf("expected help output, got %q", helpOut.String())
	}

	var stderr bytes.Buffer
	code := run([]string{"nope"}, &bytes.Buffer{}, &stderr)
	if code != 2 {
		t.Fatalf("expected unknown command exit 2, got %d", code)
	}
	if !strings.Contains(stderr.String(), `unknown command "nope"`) {
		t.Fatalf("expected unknown command message, got %q", stderr.String())
	}
}
