package main

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"time"
)

func main() {
	var keyID string
	var jsonOutput bool
	flag.StringVar(&keyID, "key-id", "", "Registry signing key id")
	flag.BoolVar(&jsonOutput, "json", false, "Emit JSON instead of shell exports")
	flag.Parse()

	if keyID == "" {
		keyID = "registry-" + time.Now().UTC().Format("20060102-150405")
	}

	publicKey, privateKey, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		fail(fmt.Sprintf("generate Ed25519 keypair: %v", err))
	}

	seed := privateKey.Seed()
	payload := map[string]string{
		"key_id":             keyID,
		"algorithm":          "ed25519",
		"private_key_seed":   base64.StdEncoding.EncodeToString(seed),
		"private_key":        base64.StdEncoding.EncodeToString(privateKey),
		"public_key":         base64.StdEncoding.EncodeToString(publicKey),
		"extra_public_entry": fmt.Sprintf("%s=%s", keyID, base64.StdEncoding.EncodeToString(publicKey)),
	}

	if jsonOutput {
		encoder := json.NewEncoder(os.Stdout)
		encoder.SetIndent("", "  ")
		if err := encoder.Encode(payload); err != nil {
			fail(fmt.Sprintf("encode keypair: %v", err))
		}
		return
	}

	fmt.Printf("ANIP_REGISTRY_KEY_ID=%s\n", payload["key_id"])
	fmt.Printf("ANIP_REGISTRY_ED25519_PRIVATE_KEY=%s\n", payload["private_key_seed"])
	fmt.Printf("# Public verification key for rotation lists:\n")
	fmt.Printf("ANIP_REGISTRY_EXTRA_PUBLIC_KEYS=%s\n", payload["extra_public_entry"])
}

func fail(message string) {
	fmt.Fprintln(os.Stderr, message)
	os.Exit(1)
}
