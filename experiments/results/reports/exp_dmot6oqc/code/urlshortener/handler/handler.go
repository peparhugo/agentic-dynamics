package handler

import (
	"encoding/json"
	"net/http"
	"net/url"
	"strings"

	"urlshortener/analytics"
	"urlshortener/codec"
	"urlshortener/ratelimit"
	"urlshortener/store"
)

type ShortenerHandler struct {
	Store     store.Store
	Codec     *codec.Generator
	Limiter   *ratelimit.Limiter
	Tracker   *analytics.Tracker
}

type shortenRequest struct {
	URL string `json:"url"`
}

type shortenResponse struct {
	Code      string `json:"code"`
	ShortURL  string `json:"short_url"`
	LongURL   string `json:"long_url"`
	CreatedAt string `json:"created_at"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func (h *ShortenerHandler) Shorten(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	ip := extractIP(r)
	if !h.Limiter.Allow("shorten:" + ip) {
		writeJSON(w, http.StatusTooManyRequests, errorResponse{Error: "rate limit exceeded"})
		return
	}

	var req shortenRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid request body"})
		return
	}
	r.Body.Close()

	if req.URL == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "url is required"})
		return
	}

	parsed, err := url.Parse(req.URL)
	if err != nil || (parsed.Scheme != "http" && parsed.Scheme != "https") {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid url"})
		return
	}

	code := h.Codec.Generate()
	entry, err := h.Store.Set(code, req.URL)
	if err != nil {
		writeJSON(w, http.StatusConflict, errorResponse{Error: err.Error()})
		return
	}

	scheme := "http"
	if r.TLS != nil {
		scheme = "https"
	}
	host := r.Host
	if fwd := r.Header.Get("X-Forwarded-Host"); fwd != "" {
		host = fwd
	}

	resp := shortenResponse{
		Code:      entry.Code,
		ShortURL:  scheme + "://" + host + "/" + entry.Code,
		LongURL:   entry.URL,
		CreatedAt: entry.CreatedAt.Format("2006-01-02T15:04:05Z"),
	}

	writeJSON(w, http.StatusCreated, resp)
}

func (h *ShortenerHandler) Redirect(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	code := strings.TrimPrefix(r.URL.Path, "/")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "code is required"})
		return
	}

	entry, err := h.Store.Get(code)
	if err != nil {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
		return
	}

	h.Store.IncrementClicks(code)
	h.Tracker.Record(code, extractIP(r), r.UserAgent(), r.Referer())

	w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate")
	w.Header().Set("Location", entry.URL)
	w.WriteHeader(http.StatusMovedPermanently)
}

func (h *ShortenerHandler) Stats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	code := strings.TrimPrefix(r.URL.Path, "/api/stats/")
	if code == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "code is required"})
		return
	}

	entry, err := h.Store.Get(code)
	if err != nil {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
		return
	}

	stats := h.Tracker.Stats(code)
	stats.TotalClicks = entry.Clicks

	writeJSON(w, http.StatusOK, stats)
}

func (h *ShortenerHandler) Health(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]interface{}{
		"status": "ok",
		"urls":   h.Store.Len(),
	})
}

func writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(data)
}

func extractIP(r *http.Request) string {
	if fwd := r.Header.Get("X-Forwarded-For"); fwd != "" {
		parts := strings.Split(fwd, ",")
		return strings.TrimSpace(parts[0])
	}
	if fwd := r.Header.Get("X-Real-IP"); fwd != "" {
		return fwd
	}
	host := r.RemoteAddr
	if idx := strings.LastIndex(host, ":"); idx != -1 {
		return host[:idx]
	}
	return host
}
