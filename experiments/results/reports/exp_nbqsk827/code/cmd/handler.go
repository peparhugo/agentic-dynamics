package cmd

import (
	"encoding/json"
	"io"
	"net/http"
	"net/url"
	"strings"

	"github.com/url-shortener/config"
	"github.com/url-shortener/shortcode"
	"github.com/url-shortener/store"
)

type Handler struct {
	store  *store.Store
	config *config.Config
}

func New(s *store.Store, c *config.Config) *Handler {
	return &Handler{store: s, config: c}
}

type shortenRequest struct {
	URL string `json:"url"`
}

type shortenResponse struct {
	Code     string `json:"code"`
	ShortURL string `json:"short_url"`
	LongURL  string `json:"long_url"`
}

type errorResponse struct {
	Error string `json:"error"`
}

func writeJSON(w http.ResponseWriter, status int, v interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func (h *Handler) Shorten(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	body, err := io.ReadAll(io.LimitReader(r.Body, int64(h.config.MaxURLBytes)))
	if err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "cannot read body"})
		return
	}
	defer r.Body.Close()

	var req shortenRequest
	if err := json.Unmarshal(body, &req); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid json"})
		return
	}

	req.URL = strings.TrimSpace(req.URL)
	if req.URL == "" {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "url is required"})
		return
	}

	if !strings.HasPrefix(req.URL, "http://") && !strings.HasPrefix(req.URL, "https://") {
		req.URL = "https://" + req.URL
	}

	if _, err := url.ParseRequestURI(req.URL); err != nil {
		writeJSON(w, http.StatusBadRequest, errorResponse{Error: "invalid url"})
		return
	}

	code, err := shortcode.Generate(h.config.CodeLength)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, errorResponse{Error: "code generation failed"})
		return
	}

	entry := h.store.Set(code, req.URL)
	resp := shortenResponse{
		Code:     entry.Code,
		ShortURL: h.config.BaseURL + "/" + entry.Code,
		LongURL:  entry.URL,
	}
	writeJSON(w, http.StatusCreated, resp)
}

func (h *Handler) Redirect(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	code := strings.TrimPrefix(r.URL.Path, "/")
	if idx := strings.IndexByte(code, '/'); idx != -1 {
		code = code[:idx]
	}

	entry, ok := h.store.Get(code)
	if !ok {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
		return
	}

	ip := r.Header.Get("X-Forwarded-For")
	if ip == "" {
		ip = r.RemoteAddr
	}
	h.store.RecordClick(code, ip, r.UserAgent(), r.Referer())

	http.Redirect(w, r, entry.URL, http.StatusMovedPermanently)
}

func (h *Handler) Analytics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		writeJSON(w, http.StatusMethodNotAllowed, errorResponse{Error: "method not allowed"})
		return
	}

	code := strings.TrimPrefix(r.URL.Path, "/analytics/")

	entry, clicks, ok := h.store.Stats(code)
	if !ok {
		writeJSON(w, http.StatusNotFound, errorResponse{Error: "not found"})
		return
	}

	response := struct {
		Code      string             `json:"code"`
		LongURL   string             `json:"long_url"`
		Clicks    int64              `json:"total_clicks"`
		CreatedAt string             `json:"created_at"`
		History   []store.ClickRecord `json:"recent_clicks"`
	}{
		Code:      entry.Code,
		LongURL:   entry.URL,
		Clicks:    entry.Clicks,
		CreatedAt: entry.CreatedAt.Format("2006-01-02T15:04:05Z"),
		History:   clicks,
	}

	writeJSON(w, http.StatusOK, response)
}
