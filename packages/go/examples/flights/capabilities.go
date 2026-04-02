package main

import (
	"crypto/rand"
	"fmt"
	"time"

	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

func floatPtr(f float64) *float64 { return &f }

func randomHex(n int) string {
	b := make([]byte, n)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}

// SearchFlights returns the search_flights capability definition.
func SearchFlights() service.CapabilityDef {
	return service.CapabilityDef{
		Declaration: core.CapabilityDeclaration{
			Name:            "search_flights",
			Description:     "Search available flights by origin, destination, and date",
			ContractVersion: "1.0",
			Inputs: []core.CapabilityInput{
				{Name: "origin", Type: "airport_code", Required: true, Description: "Departure airport"},
				{Name: "destination", Type: "airport_code", Required: true, Description: "Arrival airport"},
				{Name: "date", Type: "date", Required: true, Description: "Travel date (YYYY-MM-DD)"},
			},
			Output: core.CapabilityOutput{
				Type:   "flight_list",
				Fields: []string{"flight_number", "departure_time", "arrival_time", "price", "stops", "quote_id"},
			},
			SideEffect: core.SideEffect{
				Type:           "read",
				RollbackWindow: "not_applicable",
			},
			MinimumScope:  []string{"travel.search"},
			ResponseModes: []string{"unary"},
			RefreshVia:    []string{},
			VerifyVia:     []string{},
		},
		Handler: handleSearchFlights,
	}
}

// BookFlight returns the book_flight capability definition.
func BookFlight() service.CapabilityDef {
	return service.CapabilityDef{
		Declaration: core.CapabilityDeclaration{
			Name:            "book_flight",
			Description:     "Book a confirmed flight reservation",
			ContractVersion: "1.0",
			Inputs: []core.CapabilityInput{
				{Name: "flight_number", Type: "string", Required: true, Description: "Flight to book"},
				{Name: "date", Type: "date", Required: true, Description: "Travel date (YYYY-MM-DD)"},
				{Name: "passengers", Type: "integer", Required: false, Default: 1, Description: "Number of passengers"},
				{Name: "quote_id", Type: "object", Required: false, Description: "Priced quote from search_flights"},
			},
			Output: core.CapabilityOutput{
				Type:   "booking_confirmation",
				Fields: []string{"booking_id", "flight_number", "departure_time", "total_cost"},
			},
			SideEffect: core.SideEffect{
				Type:           "irreversible",
				RollbackWindow: "none",
			},
			MinimumScope: []string{"travel.book"},
			Cost: &core.Cost{
				Certainty: "estimated",
				Financial: &core.FinancialCost{
					Currency: "USD",
					RangeMin: floatPtr(280),
					RangeMax: floatPtr(500),
				},
				DeterminedBy: "search_flights",
			},
			Requires: []core.CapabilityRequirement{
				{
					Capability: "search_flights",
					Reason:     "must select from available flights before booking",
				},
			},
			RequiresBinding: []core.BindingRequirement{
				{
					Type:             "quote",
					Field:            "quote_id",
					SourceCapability: "search_flights",
					MaxAge:           "PT15M",
				},
			},
			ControlRequirements: []core.ControlRequirement{},
			RefreshVia:          []string{"search_flights"},
			VerifyVia:           []string{},
			ResponseModes:       []string{"unary"},
		},
		Handler: handleBookFlight,
	}
}

// --- Flight data ---

type flight struct {
	FlightNumber  string  `json:"flight_number"`
	Origin        string  `json:"origin"`
	Destination   string  `json:"destination"`
	Date          string  `json:"date"`
	DepartureTime string  `json:"departure_time"`
	ArrivalTime   string  `json:"arrival_time"`
	Price         float64 `json:"price"`
	Currency      string  `json:"currency"`
	Stops         int     `json:"stops"`
}

var flightInventory = []flight{
	{"AA100", "SEA", "SFO", "2026-03-10", "08:00", "10:15", 420.00, "USD", 0},
	{"UA205", "SEA", "SFO", "2026-03-10", "11:30", "13:45", 380.00, "USD", 0},
	{"DL310", "SEA", "SFO", "2026-03-10", "14:00", "18:30", 280.00, "USD", 1},
	{"AA101", "SEA", "SFO", "2026-03-11", "08:00", "10:15", 310.00, "USD", 0},
	{"UA450", "SEA", "LAX", "2026-03-10", "09:00", "11:30", 350.00, "USD", 0},
	{"DL520", "SFO", "JFK", "2026-03-12", "06:00", "14:30", 580.00, "USD", 0},
}

func searchFlightData(origin, destination, date string) []flight {
	var results []flight
	for _, f := range flightInventory {
		if f.Origin == origin && f.Destination == destination && f.Date == date {
			results = append(results, f)
		}
	}
	return results
}

func findFlight(flightNumber, date string) *flight {
	for _, f := range flightInventory {
		if f.FlightNumber == flightNumber && f.Date == date {
			return &f
		}
	}
	return nil
}

// --- Handlers ---

func handleSearchFlights(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
	origin, _ := params["origin"].(string)
	destination, _ := params["destination"].(string)
	date, _ := params["date"].(string)

	if origin == "" || destination == "" || date == "" {
		return nil, core.NewANIPError("invalid_parameters", "origin, destination, and date are all required")
	}

	flights := searchFlightData(origin, destination, date)
	flightMaps := make([]map[string]any, len(flights))
	for i, f := range flights {
		flightMaps[i] = map[string]any{
			"flight_number":  f.FlightNumber,
			"departure_time": f.DepartureTime,
			"arrival_time":   f.ArrivalTime,
			"price":          f.Price,
			"currency":       f.Currency,
			"stops":          f.Stops,
			"quote_id": map[string]any{
				"id":        fmt.Sprintf("qt-%s-%d", randomHex(4), time.Now().Unix()),
				"price":     f.Price,
				"issued_at": time.Now().Unix(),
			},
		}
	}

	return map[string]any{
		"flights": flightMaps,
		"count":   len(flights),
	}, nil
}

func handleBookFlight(ctx *service.InvocationContext, params map[string]any) (map[string]any, error) {
	flightNumber, _ := params["flight_number"].(string)
	date, _ := params["date"].(string)
	passengers := 1
	if p, ok := params["passengers"].(float64); ok {
		passengers = int(p)
	}

	// Accept quote_id; extract price override if provided.
	var quotedPrice float64
	if qid, ok := params["quote_id"].(map[string]any); ok {
		if p, ok := qid["price"].(float64); ok {
			quotedPrice = p
		}
	}

	if flightNumber == "" || date == "" {
		return nil, core.NewANIPError("invalid_parameters", "flight_number and date are required")
	}

	f := findFlight(flightNumber, date)
	if f == nil {
		return nil, core.NewANIPError(core.FailureUnavailable, fmt.Sprintf("flight %s on %s not found", flightNumber, date))
	}

	price := f.Price
	if quotedPrice > 0 {
		price = quotedPrice
	}
	totalCost := price * float64(passengers)

	// Generate booking ID.
	b := make([]byte, 4)
	rand.Read(b)
	bookingID := fmt.Sprintf("BK-%X", b)

	// Track actual cost.
	ctx.SetCostActual(&core.CostActual{
		Financial: &core.FinancialCost{
			Currency: f.Currency,
			Amount:   &totalCost,
		},
	})

	return map[string]any{
		"booking_id":     bookingID,
		"flight_number":  f.FlightNumber,
		"departure_time": f.DepartureTime,
		"total_cost":     totalCost,
		"currency":       f.Currency,
	}, nil
}
