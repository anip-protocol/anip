package ginapi

import (
	"net/http"

	"github.com/gin-gonic/gin"

	"github.com/anip-protocol/anip/packages/go/service"
)

// mountForTest mounts the binding under test; the tests that use it are
// shared with the net/http binding.
func mountForTest(svc *service.Service) http.Handler {
	router := gin.New()
	MountANIPGin(router, svc)
	return router
}
