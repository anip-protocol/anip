package main

import (
	"encoding/json"
	"testing"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// book_flight.quote_id is optional as far as `required` goes: the binding
// requirement is what demands it (SPEC.md §4.1, §6.3).
func TestBookFlightDeclaration(t *testing.T) {
	required := map[string]bool{}
	for _, input := range BookFlight().Declaration.Inputs {
		required[input.Name] = input.Required
	}
	want := map[string]bool{"flight_number": true, "date": true, "passengers": false, "quote_id": false}
	for name, wantRequired := range want {
		if got, declared := required[name]; !declared || got != wantRequired {
			t.Errorf("%s: required = %v (declared %v), want %v", name, got, declared, wantRequired)
		}
	}
}

// An integral float is the integer it equals: the booking is made for that
// many passengers, whichever in-memory form a binding hands over.
func TestBookFlightAcceptsEveryIntegerForm(t *testing.T) {
	for name, passengers := range map[string]any{
		"float64":     2.0,
		"int":         2,
		"int64":       int64(2),
		"json.Number": json.Number("2.0"),
	} {
		t.Run(name, func(t *testing.T) {
			ctx := &service.InvocationContext{Token: &core.DelegationToken{}}
			result, err := handleBookFlight(ctx, map[string]any{
				"flight_number": "AA100",
				"date":          "2026-03-10",
				"passengers":    passengers,
				"quote_id":      map[string]any{"id": "qt-1", "price": 420.0},
			})
			if err != nil {
				t.Fatalf("handleBookFlight: %v", err)
			}
			if result["total_cost"] != 840.0 {
				t.Fatalf("total_cost = %v, want 840 (two passengers at 420)", result["total_cost"])
			}
		})
	}
}
