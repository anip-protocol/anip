// Package main implements an example ANIP flight service using Gin.
// Same capabilities as the net/http example, proving Gin binding conformance.
package main

import (
	"log"
	"os"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/ginapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

func main() {
	svc := service.New(service.Config{
		ServiceID:    "anip-flight-service",
		Capabilities: []service.CapabilityDef{SearchFlights(), BookFlight()},
		Storage:      "sqlite:///anip-gin.db",
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

	gin.SetMode(gin.ReleaseMode)
	router := gin.New()
	ginapi.MountANIPGin(router, svc)

	addr := ":8080"
	if port := os.Getenv("PORT"); port != "" {
		addr = ":" + port
	}

	log.Printf("ANIP Flight Service (Go/Gin) running on http://localhost%s", addr)
	if err := router.Run(addr); err != nil {
		log.Fatal(err)
	}
}
