package verify

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"

	"github.com/anip-protocol/anip/packages/go/verifier"
)

type cliError struct {
	message string
	code    int
}

func Run(args []string, stdout io.Writer, stderr io.Writer) (exitCode int) {
	if stdout == nil {
		stdout = os.Stdout
	}
	if stderr == nil {
		stderr = os.Stderr
	}
	defer func() {
		if recovered := recover(); recovered != nil {
			if err, ok := recovered.(cliError); ok {
				fmt.Fprintln(stderr, err.message)
				exitCode = err.code
				return
			}
			panic(recovered)
		}
	}()

	var definitionPath string
	var packageBundle string
	var registryBase string
	var registryURL string
	var packageID string
	var packageVersion string
	var packageRef string
	var lockFile string
	var expectedContractSignature string
	var requiredRegistryMode string
	var trustedRegistryKeyID string
	var allowYankedPackage bool

	fs := flag.NewFlagSet("anip validate", flag.ContinueOnError)
	if hasHelpFlag(args) {
		fs.SetOutput(stdout)
	} else {
		fs.SetOutput(stderr)
	}
	fs.Usage = func() {
		writer := fs.Output()
		fmt.Fprintln(writer, `Usage:
  anip validate --definition <file> [flags]
  anip validate --package-bundle <bundle> [flags]
  anip validate --registry-url <url> --package <id@version> [flags]

Compatibility:
  anip verify [flags] and anip-verify [flags] run the same command.

Flags:`)
		fs.PrintDefaults()
	}
	fs.StringVar(&definitionPath, "definition", "", "Path to a local anip-service-definition.json")
	fs.StringVar(&packageBundle, "package-bundle", "", "Path to a portable .anip-package.json bundle")
	fs.StringVar(&registryBase, "registry-base", "", "Base URL of the ANIP Registry service")
	fs.StringVar(&registryURL, "registry-url", "", "Base URL of the ANIP Registry service")
	fs.StringVar(&packageID, "package-id", "", "Registry package id")
	fs.StringVar(&packageVersion, "package-version", "", "Registry package version")
	fs.StringVar(&packageRef, "package", "", "Registry package reference as package_id@package_version")
	fs.StringVar(&lockFile, "lock-file", "", "Path to an anip package lock file to enforce during validation")
	fs.StringVar(&expectedContractSignature, "expected-contract-signature", "", "Expected compiled contract signature")
	fs.StringVar(&requiredRegistryMode, "require-registry-mode", "", "Required Registry signing mode, for example production")
	fs.StringVar(&trustedRegistryKeyID, "trusted-registry-key-id", "", "Trusted Registry receipt signing key id")
	fs.BoolVar(&allowYankedPackage, "allow-yanked-package", false, "Allow validating a yanked registry package for pinned historical reproduction. Takedown packages are always blocked.")
	if err := fs.Parse(args); err != nil {
		if err == flag.ErrHelp {
			return 0
		}
		return 2
	}
	if registryURL != "" {
		registryBase = registryURL
	}

	result, err := verifier.VerifyServiceDefinition(context.Background(), nil, verifier.VerifyOptions{
		DefinitionPath:            definitionPath,
		PackageBundle:             packageBundle,
		RegistryBase:              registryBase,
		PackageID:                 packageID,
		PackageVersion:            packageVersion,
		PackageRef:                packageRef,
		LockFile:                  lockFile,
		ExpectedContractSignature: expectedContractSignature,
		RequiredRegistryMode:      requiredRegistryMode,
		TrustedRegistryKeyID:      trustedRegistryKeyID,
		AllowYankedPackage:        allowYankedPackage,
	})
	if err != nil {
		fail(err.Error(), 1)
	}

	encoder := json.NewEncoder(stdout)
	encoder.SetIndent("", "  ")
	_ = encoder.Encode(result)
	if result.Status != "ok" {
		return 2
	}
	return 0
}

func fail(message string, code int) {
	panic(cliError{message: message, code: code})
}

func hasHelpFlag(args []string) bool {
	for _, arg := range args {
		if arg == "-h" || arg == "--help" {
			return true
		}
	}
	return false
}
