package main

import (
	"log"
	"net/http"
	"os"

	"urlshortener/analytics"
	"urlshortener/codec"
	"urlshortener/handler"
	"urlshortener/middleware"
	"urlshortener/ratelimit"
	"urlshortener/store"
)

func main() {
	st := store.NewMemoryStore()
	codecGen := codec.NewGenerator()
	limiter := ratelimit.NewLimiter(100, 200)
	tracker := analytics.NewTracker(10000)

	h := &handler.ShortenerHandler{
		Store:   st,
		Codec:   codecGen,
		Limiter: limiter,
		Tracker: tracker,
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/api/shorten", h.Shorten)
	mux.HandleFunc("/api/stats/", h.Stats)
	mux.HandleFunc("/health", h.Health)

	mux.HandleFunc("/", h.Redirect)

	var srv http.Handler = mux
	srv = middleware.Logger(srv)
	srv = middleware.Recoverer(srv)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8080"
	}

	log.Printf("URL shortener starting on :%s", port)
	if err := http.ListenAndServe(":"+port, srv); err != nil {
		log.Fatalf("server error: %v", err)
	}
}
