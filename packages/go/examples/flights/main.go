// Package main implements an example ANIP flight service using the Go runtime.
package main

import (
	"log"
	"net/http"
	"os"

	"github.com/anip-protocol/anip/packages/go/httpapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

func main() {
	svc := service.New(service.Config{
		ServiceID:    "anip-flight-service",
		Capabilities: []service.CapabilityDef{SearchFlights(), BookFlight()},
		Storage:      "sqlite:///anip.db",
		Trust:        "signed",
		KeyPath:      "./anip-keys",
		Authenticate: func(bearer string) (string, bool) {
			keys := map[string]string{
				"demo-human-key": "human:samir@example.com",
				"demo-agent-key": "agent:demo-agent",
			}
			p, ok := keys[bearer]
			return p, ok
		},
	})

	if err := svc.Start(); err != nil {
		log.Fatalf("Failed to start service: %v", err)
	}
	defer svc.Shutdown()

	mux := http.NewServeMux()
	httpapi.MountANIP(mux, svc)

	addr := ":8080"
	if port := os.Getenv("PORT"); port != "" {
		addr = ":" + port
	}

	log.Printf("ANIP Flight Service (Go) running on http://localhost%s", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}
