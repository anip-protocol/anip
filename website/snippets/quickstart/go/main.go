package main

import (
	"log"
	"net/http"
	"os"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/httpapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

// Your business logic. Nothing here knows about ANIP.
func doSearch(origin, destination string) []map[string]any {
	return []map[string]any{
		{"flight_number": "AA100", "origin": origin, "destination": destination, "price": 420},
		{"flight_number": "DL310", "origin": origin, "destination": destination, "price": 280},
	}
}

func doBook(flightNumber string) map[string]any {
	return map[string]any{"booking_id": "BK-0001", "flight_number": flightNumber}
}

// A capability that only reads.
var searchFlights = service.CapabilityDef{
	Declaration: core.CapabilityDeclaration{
		Name:            "search_flights",
		Description:     "Search available flights between two airports",
		ContractVersion: "1.0",
		Inputs: []core.CapabilityInput{
			{Name: "origin", Type: "string", Required: true, Description: "Departure airport"},
			{Name: "destination", Type: "string", Required: true, Description: "Arrival airport"},
		},
		Output:       core.CapabilityOutput{Type: "object", Fields: []string{"flights"}},
		SideEffect:   core.SideEffect{Type: "read", RollbackWindow: "not_applicable"},
		MinimumScope: []string{"travel.search"},
	},
	Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
		origin, _ := params["origin"].(string)
		destination, _ := params["destination"].(string)
		return map[string]any{"flights": doSearch(origin, destination)}, nil
	},
}

// A capability that cannot be undone, and needs a different scope.
var bookFlight = service.CapabilityDef{
	Declaration: core.CapabilityDeclaration{
		Name:            "book_flight",
		Description:     "Book a flight",
		ContractVersion: "1.0",
		Inputs: []core.CapabilityInput{
			{Name: "flight_number", Type: "string", Required: true, Description: "Flight to book"},
		},
		Output:       core.CapabilityOutput{Type: "object", Fields: []string{"booking_id", "flight_number"}},
		SideEffect:   core.SideEffect{Type: "irreversible", RollbackWindow: "none"},
		MinimumScope: []string{"travel.book"},
	},
	Handler: func(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
		flightNumber, _ := params["flight_number"].(string)
		return doBook(flightNumber), nil
	},
}

func main() {
	svc := service.New(service.Config{
		ServiceID:    "quickstart-flights",
		Capabilities: []service.CapabilityDef{searchFlights, bookFlight},
		Storage:      ":memory:",
		Trust:        "signed",
		// Who is calling? Map your own API keys or sessions to a principal.
		Authenticate: func(bearer string) (string, bool) {
			principal, ok := map[string]string{"demo-key": "human:demo@example.com"}[bearer]
			return principal, ok
		},
	})
	if err := svc.Start(); err != nil {
		log.Fatal(err)
	}
	defer svc.Shutdown()

	mux := http.NewServeMux()
	httpapi.MountANIP(mux, svc)

	port := os.Getenv("PORT")
	if port == "" {
		port = "9100"
	}
	log.Fatal(http.ListenAndServe(":"+port, mux))
}
