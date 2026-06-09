package main

import (
	"os"

	generatecmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/generate"
)

func main() {
	os.Exit(generatecmd.Run(os.Args[1:], os.Stdout, os.Stderr))
}
