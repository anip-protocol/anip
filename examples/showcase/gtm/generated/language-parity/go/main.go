package main

import (
	"context"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"strconv"
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
	port := envInt("PORT", 4100)
	server := &http.Server{
		Addr: fmt.Sprintf(":%d", port),
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
