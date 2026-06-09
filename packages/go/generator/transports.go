package generator

import (
	"fmt"
	"strings"
)

func normalizeTransports(values []Transport) ([]Transport, error) {
	if len(values) == 0 {
		return []Transport{TransportHTTP}, nil
	}
	seen := map[Transport]struct{}{}
	result := []Transport{}
	for _, raw := range values {
		value := Transport(strings.TrimSpace(string(raw)))
		if value == "" {
			continue
		}
		switch value {
		case TransportHTTP, TransportStdio:
			if _, ok := seen[value]; !ok {
				seen[value] = struct{}{}
				result = append(result, value)
			}
		default:
			return nil, fmt.Errorf("unsupported transport %q", value)
		}
	}
	if len(result) == 0 {
		return []Transport{TransportHTTP}, nil
	}
	if _, ok := seen[TransportHTTP]; !ok {
		result = append([]Transport{TransportHTTP}, result...)
	}
	return result, nil
}

func hasTransport(values []Transport, target Transport) bool {
	for _, value := range values {
		if value == target {
			return true
		}
	}
	return false
}

func ParseTransportList(raw string) ([]Transport, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" {
		return []Transport{TransportHTTP}, nil
	}
	parts := strings.Split(trimmed, ",")
	values := make([]Transport, 0, len(parts))
	for _, part := range parts {
		values = append(values, Transport(strings.TrimSpace(part)))
	}
	return normalizeTransports(values)
}

func TransportNames(values []Transport) []string {
	result := make([]string, 0, len(values))
	for _, value := range values {
		result = append(result, string(value))
	}
	return result
}
