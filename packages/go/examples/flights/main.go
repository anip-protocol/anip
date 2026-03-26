// Package main implements an example ANIP flight service using the Go runtime.
package main

import (
	"log"
	"net/http"
	"os"

	"github.com/anip-protocol/anip/packages/go/graphqlapi"
	"github.com/anip-protocol/anip/packages/go/httpapi"
	"github.com/anip-protocol/anip/packages/go/mcpapi"
	"github.com/anip-protocol/anip/packages/go/restapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

func main() {
	serviceID := os.Getenv("ANIP_SERVICE_ID")
	if serviceID == "" {
		serviceID = "anip-flight-service"
	}

	// Optional OIDC authentication — enabled when OIDC_ISSUER_URL is set
	var oidcValidator *OIDCValidator
	if issuerURL := os.Getenv("OIDC_ISSUER_URL"); issuerURL != "" {
		audience := os.Getenv("OIDC_AUDIENCE")
		if audience == "" {
			audience = serviceID
		}
		oidcValidator = NewOIDCValidator(issuerURL, audience, os.Getenv("OIDC_JWKS_URL"))
	}

	keys := map[string]string{
		"demo-human-key": "human:samir@example.com",
		"demo-agent-key": "agent:demo-agent",
	}

	svc := service.New(service.Config{
		ServiceID:    serviceID,
		Capabilities: []service.CapabilityDef{SearchFlights(), BookFlight()},
		Storage:      "sqlite:///anip.db",
		Trust:        "signed",
		KeyPath:      "./anip-keys",
		Authenticate: func(bearer string) (string, bool) {
			// 1. API key map
			if p, ok := keys[bearer]; ok {
				return p, true
			}
			// 2. OIDC (if configured)
			if oidcValidator != nil {
				if p, ok := oidcValidator.Validate(bearer); ok {
					return p, true
				}
			}
			return "", false
		},
	})

	if err := svc.Start(); err != nil {
		log.Fatalf("Failed to start service: %v", err)
	}
	defer svc.Shutdown()

	mux := http.NewServeMux()
	httpapi.MountANIP(mux, svc)
	restapi.MountANIPRest(mux, svc, nil)
	graphqlapi.MountANIPGraphQL(mux, svc, nil)
	mcpapi.MountAnipMcpHTTP(mux, svc, nil)

	addr := ":9200"
	if port := os.Getenv("PORT"); port != "" {
		addr = ":" + port
	}

	log.Printf("ANIP Flight Service (Go) running on http://localhost%s", addr)
	log.Printf("  ANIP protocol: http://localhost%s/anip/", addr)
	log.Printf("  REST API:      http://localhost%s/rest/openapi.json", addr)
	log.Printf("  GraphQL:       http://localhost%s/graphql", addr)
	log.Printf("  MCP:           http://localhost%s/mcp", addr)
	if err := http.ListenAndServe(addr, mux); err != nil {
		log.Fatal(err)
	}
}
