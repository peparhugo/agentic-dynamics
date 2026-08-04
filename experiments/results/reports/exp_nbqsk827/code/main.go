package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"

	"github.com/url-shortener/cmd"
	"github.com/url-shortener/config"
	"github.com/url-shortener/ratelimit"
	"github.com/url-shortener/store"
)

func main() {
	cfg := config.Load()
	st := store.New()
	limiter := ratelimit.NewLimiter(cfg.RateLimitRPS, cfg.RateLimitBurst)
	h := cmd.New(st, cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("/shorten", h.Shorten)
	mux.HandleFunc("/analytics/", h.Analytics)
	mux.HandleFunc("/", h.Redirect)

	var handler http.Handler = mux
	handler = ratelimit.Middleware(limiter)(handler)

	srv := &http.Server{
		Addr:         ":" + cfg.Port,
		Handler:      handler,
		ReadTimeout:  cfg.ReadTimeout,
		WriteTimeout: cfg.WriteTimeout,
	}

	go func() {
		log.Printf("URL shortener listening on :%s", cfg.Port)
		log.Printf("Base URL: %s", cfg.BaseURL)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("shutting down...")

	ctx, cancel := context.WithTimeout(context.Background(), cfg.ShutdownTimeout)
	defer cancel()
	if err := srv.Shutdown(ctx); err != nil {
		log.Fatalf("shutdown: %s", err)
	}
	log.Println("server stopped")
}
