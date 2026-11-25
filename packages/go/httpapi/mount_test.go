package httpapi

import (
	"net/http"

	"github.com/anip-protocol/anip/packages/go/service"
)

// mountForTest mounts the binding under test; the tests that use it are
// shared with the gin binding.
func mountForTest(svc *service.Service) http.Handler {
	mux := http.NewServeMux()
	MountANIP(mux, svc)
	return mux
}
