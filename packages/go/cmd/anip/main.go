package main

import (
	"fmt"
	"io"
	"os"

	"github.com/anip-protocol/anip/packages/go/core"
	frontingcmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/fronting"
	generatecmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/generate"
	packagecmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/packagecmd"
	verifycmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/verify"
)

var version = "0.8.0"

func main() {
	os.Exit(run(os.Args[1:], os.Stdout, os.Stderr))
}

func run(args []string, stdout io.Writer, stderr io.Writer) int {
	if len(args) == 0 {
		printUsage(stderr)
		return 2
	}

	switch args[0] {
	case "fronting":
		return frontingcmd.Run(args[1:], stdout, stderr)
	case "generate":
		return generatecmd.Run(args[1:], stdout, stderr)
	case "package":
		return packagecmd.Run(args[1:], stdout, stderr)
	case "validate", "verify":
		return verifycmd.Run(args[1:], stdout, stderr)
	case "version":
		printVersion(stdout)
		return 0
	case "--version":
		printVersion(stdout)
		return 0
	case "help", "-h", "--help":
		printUsage(stdout)
		return 0
	default:
		fmt.Fprintf(stderr, "unknown command %q\n", args[0])
		printUsage(stderr)
		return 2
	}
}

func printVersion(writer io.Writer) {
	fmt.Fprintf(writer, "anip CLI %s\n", version)
	fmt.Fprintf(writer, "ANIP spec %s\n", core.ProtocolVersion)
}

func printUsage(writer io.Writer) {
	fmt.Fprintln(writer, `Usage:
  anip generate [flags]
  anip fronting scaffold [flags]
  anip package build-local [flags]
  anip package publish-bundle [flags]
  anip package attach-implementation [flags]
  anip package audit-effects [flags]
  anip validate [flags]
  anip verify [flags]
  anip version

Compatibility:
  anip-generate and anip-verify remain available.`)
}
