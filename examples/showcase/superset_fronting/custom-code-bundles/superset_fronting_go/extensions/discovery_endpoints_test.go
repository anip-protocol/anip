package extensions

import (
	"reflect"
	"testing"
)

func discoveryKinds(assetType string) []string {
	kinds := []string{}
	for _, endpoint := range discoveryEndpoints(assetType) {
		kinds = append(kinds, endpoint[0])
	}
	return kinds
}

// "all" is asset_type's declared default, so it is what a call without
// asset_type carries; it must not filter out every endpoint.
func TestDiscoveryEndpointsPerAssetType(t *testing.T) {
	every := []string{"dataset", "chart", "dashboard"}
	for assetType, want := range map[string][]string{
		"all":    every,
		"":       every,
		"chart":  {"chart"},
		"metric": {},
	} {
		if got := discoveryKinds(assetType); !reflect.DeepEqual(got, want) {
			t.Fatalf("asset_type %q: expected %v, got %v", assetType, want, got)
		}
	}
}
