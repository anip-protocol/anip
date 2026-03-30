// Package studioapi mounts the ANIP Studio inspection UI on an http.ServeMux.
package studioapi

import (
	"embed"
	"encoding/json"
	"io/fs"
	"net/http"
	"strings"
)

//go:embed static/*
var staticFiles embed.FS

type studioConfig struct {
	ServiceID string `json:"service_id"`
	Embedded  bool   `json:"embedded"`
}

// MountANIPStudio serves the Studio SPA at the given prefix (default "/studio").
// The serviceID is included in the bootstrap config.json.
func MountANIPStudio(mux *http.ServeMux, serviceID string, prefix ...string) {
	p := "/studio"
	if len(prefix) > 0 && prefix[0] != "" {
		p = prefix[0]
	}
	if !strings.HasPrefix(p, "/") {
		p = "/" + p
	}
	p = strings.TrimSuffix(p, "/")

	// Serve embedded static files
	staticFS, err := fs.Sub(staticFiles, "static")
	if err != nil {
		return
	}
	fileServer := http.FileServer(http.FS(staticFS))

	// Config endpoint
	mux.HandleFunc(p+"/config.json", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(studioConfig{
			ServiceID: serviceID,
			Embedded:  true,
		})
	})

	// All other routes — try static file, fallback to index.html
	mux.HandleFunc(p+"/", func(w http.ResponseWriter, r *http.Request) {
		// Strip prefix for file lookup
		path := strings.TrimPrefix(r.URL.Path, p+"/")
		if path == "" {
			path = "index.html"
		}

		// Try to open the file
		f, err := staticFS.Open(path)
		if err == nil {
			f.Close()
			// Set cache headers for hashed assets
			if strings.HasPrefix(path, "assets/") {
				w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
			}
			fileServer.ServeHTTP(w, r)
			return
		}

		// SPA fallback — serve index.html
		indexData, err := fs.ReadFile(staticFS, "index.html")
		if err != nil {
			http.Error(w, "Studio not available", http.StatusInternalServerError)
			return
		}
		w.Header().Set("Content-Type", "text/html")
		w.Write(indexData)
	})

	// Handle /studio without trailing slash
	mux.HandleFunc(p, func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, p+"/", http.StatusMovedPermanently)
	})
}
