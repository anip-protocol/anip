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

	"github.com/anip-protocol/anip/examples/showcase/notion_fronting/generated/language-parity/go/app"
	"github.com/anip-protocol/anip/packages/go/stdioapi"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "--stdio" {
		runStdio()
		return
	}

	svc, err := app.NewService()
	if err != nil {
		log.Fatalf("start service: %v", err)
	}
	defer svc.Shutdown()

	mux := app.NewMux(svc)
	port := envInt("PORT", 9164)
	server := &http.Server{
		Addr: fmt.Sprintf(":%d", port),
		Handler: mux,
}

	log.Printf("Notion Fronting Showcase 0.2.0 running on http://localhost:%d", port)
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

func runStdio() {
	svc, err := app.NewService()
	if err != nil {
		log.Fatalf("start service: %v", err)
	}
	if err := stdioapi.ServeStdio(svc); err != nil {
		log.Fatalf("stdio: %v", err)
	}
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
