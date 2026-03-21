// Package restapi auto-generates REST endpoints from ANIP capabilities.
package restapi

import (
	"github.com/anip-protocol/anip/packages/go/core"
	"github.com/anip-protocol/anip/packages/go/service"
)

// RouteOverride allows customizing the path and/or method for a capability route.
type RouteOverride struct {
	Path   string
	Method string
}

// RESTRoute represents a single REST endpoint generated from an ANIP capability.
type RESTRoute struct {
	CapabilityName string
	Path           string
	Method         string // "GET" or "POST"
	Declaration    core.CapabilityDeclaration
}

// RestOptions configures REST endpoint generation and mounting.
type RestOptions struct {
	Routes map[string]RouteOverride // capability name -> custom path/method
	Prefix string                   // URL prefix, default ""
}

// GenerateRoutes generates REST routes from service capabilities.
// Default: GET for read side_effect, POST for everything else.
// Overrides replace path and/or method.
func GenerateRoutes(svc *service.Service, overrides map[string]RouteOverride) []RESTRoute {
	manifest := svc.GetManifest()
	var routes []RESTRoute

	for name, decl := range manifest.Capabilities {
		override, hasOverride := overrides[name]

		path := "/api/" + name
		method := "POST"
		if decl.SideEffect.Type == "read" {
			method = "GET"
		}

		if hasOverride {
			if override.Path != "" {
				path = override.Path
			}
			if override.Method != "" {
				method = override.Method
			}
		}

		routes = append(routes, RESTRoute{
			CapabilityName: name,
			Path:           path,
			Method:         method,
			Declaration:    decl,
		})
	}

	return routes
}
