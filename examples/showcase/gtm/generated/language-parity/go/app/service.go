package app

import (
	"encoding/json"
	"net/http"
	"os"
	"strings"

	"generated/gtm-operator-contract-20260512235040/generated"
	"generated/gtm-operator-contract-20260512235040/host"
	"github.com/anip-protocol/anip/packages/go/httpapi"
	"github.com/anip-protocol/anip/packages/go/service"
)

func readAPIKeys() map[string]string {
	raw := os.Getenv("ANIP_API_KEYS_JSON")
	if strings.TrimSpace(raw) == "" {
		return map[string]string{"dev-admin-key": "human:local-developer", "demo-human-key": "human:generated", "demo-agent-key": "agent:generated-service"}
	}
	var decoded map[string]string
	if err := json.Unmarshal([]byte(raw), &decoded); err != nil {
		return map[string]string{"dev-admin-key": "human:local-developer"}
	}
	return decoded
}

func NewService() (*service.Service, error) {
	apiKeys := readAPIKeys()
	serviceID := os.Getenv("ANIP_SERVICE_ID")
	if strings.TrimSpace(serviceID) == "" {
		serviceID = generated.RuntimeTarget.SystemName
	}
	svc := service.New(service.Config{
		ServiceID: serviceID,
		Capabilities: host.GeneratedCapabilities,
		Storage: firstNonEmpty(os.Getenv("ANIP_STORAGE"), ":memory:"),
		Trust: firstNonEmpty(os.Getenv("ANIP_TRUST_LEVEL"), "signed"),
		KeyPath: firstNonEmpty(os.Getenv("ANIP_KEY_PATH"), "./anip-keys"),
		Authenticate: func(bearer string) (string, bool) {
			principal, ok := apiKeys[bearer]
			return principal, ok
		},
	})
	if err := svc.Start(); err != nil {
		return nil, err
	}
	return svc, nil
}

func NewMux(svc *service.Service) *http.ServeMux {
	mux := http.NewServeMux()
	httpapi.MountANIP(mux, svc, httpapi.MountANIPOpts{HealthEndpoint: true})
	return mux
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
