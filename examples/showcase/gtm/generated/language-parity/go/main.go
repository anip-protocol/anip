package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"generated/gtm-operator-contract-20260512235040/app"
	"generated/gtm-operator-contract-20260512235040/extensions"
)

func main() {
	svc, err := app.NewService()
	if err != nil {
		log.Fatalf("start service: %v", err)
	}
	defer svc.Shutdown()

	mux := app.NewMux(svc)
	mountApprovals(mux)

	port := envInt("PORT", 4200)
	server := &http.Server{Addr: fmt.Sprintf(":%d", port), Handler: mux}

	log.Printf("GTM Go native service running on http://localhost:%d", port)
	go func() {
		if err := server.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen and serve: %v", err)
		}
	}()

	signals := make(chan os.Signal, 1)
	signal.Notify(signals, syscall.SIGINT, syscall.SIGTERM)
	<-signals

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = server.Shutdown(ctx)
}

func envInt(name string, fallback int) int {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return fallback
	}
	return value
}

func mountApprovals(mux *http.ServeMux) {
	mux.HandleFunc("/gtm/approvals", listApprovals)
	mux.HandleFunc("/gtm/approvals/", approveRequest)
	mux.HandleFunc("/gtm/pipeline/approvals", listApprovals)
	mux.HandleFunc("/gtm/pipeline/approvals/", approveRequest)
	mux.HandleFunc("/gtm/prioritization/approvals", listApprovals)
	mux.HandleFunc("/gtm/prioritization/approvals/", approveRequest)
}

func listApprovals(response http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodGet {
		http.Error(response, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	status := request.URL.Query().Get("status")
	writeJSON(response, http.StatusOK, map[string]any{"entries": extensions.ListApprovalRequests(status)})
}

func approveRequest(response http.ResponseWriter, request *http.Request) {
	if request.Method != http.MethodPost {
		http.Error(response, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	id := approvalIDFromPath(request.URL.Path)
	if id == "" {
		http.Error(response, "approval_request_id is required", http.StatusBadRequest)
		return
	}
	actor, ok := extensions.ActorFromBearer(strings.TrimPrefix(request.Header.Get("authorization"), "Bearer "))
	if !ok {
		http.Error(response, "invalid bearer token", http.StatusUnauthorized)
		return
	}
	record, ok := extensions.ApproveRequest(id, actor)
	if !ok {
		http.Error(response, "approval request not found", http.StatusNotFound)
		return
	}
	writeJSON(response, http.StatusOK, map[string]any{"approval": record})
}

func approvalIDFromPath(path string) string {
	parts := strings.Split(strings.Trim(path, "/"), "/")
	for index, part := range parts {
		if part == "approvals" && index+1 < len(parts) {
			return parts[index+1]
		}
	}
	return ""
}

func writeJSON(response http.ResponseWriter, status int, payload map[string]any) {
	response.Header().Set("content-type", "application/json")
	response.WriteHeader(status)
	_ = json.NewEncoder(response).Encode(payload)
}
