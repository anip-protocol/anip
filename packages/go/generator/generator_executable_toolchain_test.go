package generator

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// Exercise generated code with the SDK's reviewed test tools, not whichever
// Vitest/Vite releases happen to satisfy floating ranges on the day of the run.
// This does not test fresh resolution of the generated dependency ranges.
func installConformanceTypeScriptTools(t *testing.T, outputDir, repoRoot string, env []string) {
	t.Helper()
	for _, name := range []string{"node", "npm"} {
		cmd := exec.Command(name, "--version")
		cmd.Dir = outputDir
		cmd.Env = env
		output, err := cmd.CombinedOutput()
		if err != nil {
			t.Fatalf("read %s version: %v\n%s", name, err, output)
		}
		t.Logf("conformance runtime toolchain: %s %s (%s)", name, strings.TrimSpace(string(output)), cmd.Path)
	}
	lockBytes, err := os.ReadFile(filepath.Join(repoRoot, "packages/typescript/package-lock.json"))
	if err != nil {
		t.Fatal(err)
	}
	var lock struct {
		Packages map[string]struct {
			Version string `json:"version"`
		} `json:"packages"`
	}
	if err := json.Unmarshal(lockBytes, &lock); err != nil {
		t.Fatal(err)
	}
	versions := map[string]string{}
	for _, name := range []string{"vitest", "vite", "rolldown", "postcss"} {
		version := lock.Packages["node_modules/"+name].Version
		if !regexp.MustCompile(`^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$`).MatchString(version) {
			t.Fatalf("SDK lock has no exact %s version: %q", name, version)
		}
		versions[name] = version
		t.Logf("conformance test toolchain: %s@%s", name, version)
	}
	manifestPath := filepath.Join(outputDir, "package.json")
	before, err := os.ReadFile(manifestPath)
	if err != nil {
		t.Fatal(err)
	}
	runConformanceCommand(t, outputDir, env, "npm", "install", "--ignore-scripts", "--prefer-offline",
		"--no-save", "--package-lock=false", "vitest@"+versions["vitest"], "vite@"+versions["vite"], "rolldown@"+versions["rolldown"], "postcss@"+versions["postcss"])
	after, err := os.ReadFile(manifestPath)
	if err != nil || !bytes.Equal(before, after) {
		t.Fatalf("test tool installation changed generated package.json: %v", err)
	}
	for _, name := range []string{"vitest", "vite", "rolldown", "postcss"} {
		raw, err := os.ReadFile(filepath.Join(outputDir, "node_modules", name, "package.json"))
		if err != nil {
			t.Fatal(err)
		}
		var installed struct {
			Version string `json:"version"`
		}
		if err := json.Unmarshal(raw, &installed); err != nil {
			t.Fatal(err)
		}
		if installed.Version != versions[name] {
			t.Fatalf("installed %s@%s, expected SDK toolchain %s", name, installed.Version, versions[name])
		}
	}
}
