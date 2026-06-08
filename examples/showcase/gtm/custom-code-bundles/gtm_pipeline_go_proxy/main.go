package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"

	"generated/gtm-pipeline-q2-review/app"
)

func main() {
	svc, err := app.NewService()
	if err != nil {
		log.Fatalf("start service: %v", err)
	}
	defer svc.Shutdown()

	mux := app.NewMux(svc)
	mountApprovalProxies(mux)

	port := envInt("PORT", 4100)
	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: mux,
	}

	log.Printf("GTM Pipeline Q2 Review running on http://localhost:%d", port)
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

func mountApprovalProxies(mux *http.ServeMux) {
	mux.HandleFunc("/gtm/approvals", proxyApproval("gtm-pipeline-service", "/gtm/approvals"))
	mux.HandleFunc("/gtm/pipeline/approvals", proxyApproval("gtm-pipeline-service", "/gtm/approvals"))
	mux.HandleFunc("/gtm/pipeline/approvals/", proxyApprovalPrefix("gtm-pipeline-service", "/gtm/pipeline/approvals/", "/gtm/approvals/"))
	mux.HandleFunc("/gtm/prioritization/approvals", proxyApproval("gtm-prioritization-service", "/gtm/approvals"))
	mux.HandleFunc("/gtm/prioritization/approvals/", proxyApprovalPrefix("gtm-prioritization-service", "/gtm/prioritization/approvals/", "/gtm/approvals/"))
}

func proxyApproval(serviceID string, path string) http.HandlerFunc {
	return func(response http.ResponseWriter, request *http.Request) {
		proxyToDownstream(response, request, serviceID, path)
	}
}

func proxyApprovalPrefix(serviceID string, sourcePrefix string, targetPrefix string) http.HandlerFunc {
	return func(response http.ResponseWriter, request *http.Request) {
		suffix := strings.TrimPrefix(request.URL.Path, sourcePrefix)
		proxyToDownstream(response, request, serviceID, targetPrefix+suffix)
	}
}

func proxyToDownstream(response http.ResponseWriter, request *http.Request, serviceID string, path string) {
	serviceURL := strings.TrimRight(downstreamServices()[serviceID], "/")
	if serviceURL == "" {
		http.Error(response, "downstream service URL is not configured", http.StatusServiceUnavailable)
		return
	}
	target, err := http.NewRequest(request.Method, serviceURL+path, nil)
	if err != nil {
		http.Error(response, err.Error(), http.StatusInternalServerError)
		return
	}
	target.Header.Set("authorization", request.Header.Get("authorization"))
	downstreamResponse, err := http.DefaultClient.Do(target)
	if err != nil {
		http.Error(response, err.Error(), http.StatusBadGateway)
		return
	}
	defer downstreamResponse.Body.Close()
	response.Header().Set("content-type", downstreamResponse.Header.Get("content-type"))
	response.WriteHeader(downstreamResponse.StatusCode)
	_, _ = io.Copy(response, downstreamResponse.Body)
}

func downstreamServices() map[string]string {
	return map[string]string{
		"gtm-pipeline-service":       firstNonEmpty(os.Getenv("GTM_PIPELINE_SERVICE_URL"), "http://127.0.0.1:4100"),
		"gtm-prioritization-service": firstNonEmpty(os.Getenv("GTM_PRIORITIZATION_SERVICE_URL"), "http://127.0.0.1:4102"),
	}
}

func firstNonEmpty(values ...string) string {
	for _, value := range values {
		if strings.TrimSpace(value) != "" {
			return value
		}
	}
	return ""
}
