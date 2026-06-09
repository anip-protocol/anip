package main

import (
	"os"

	verifycmd "github.com/anip-protocol/anip/packages/go/internal/clicommands/verify"
)

func main() {
	os.Exit(verifycmd.Run(os.Args[1:], os.Stdout, os.Stderr))
}
