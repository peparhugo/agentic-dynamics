package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/url-shortener/cmd"
	"github.com/url-shortener/config"
	"github.com/url-shortener/store"
)

func TestShorten(t *testing.T) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	body := `{"url":"https://example.com/very/long/path"}`
	req := httptest.NewRequest(http.MethodPost, "/shorten", strings.NewReader(body))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()

	h.Shorten(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("expected 201, got %d", resp.StatusCode)
	}

	var m map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&m)
	if m["short_url"] == nil || m["short_url"] == "" {
		t.Fatal("expected short_url in response")
	}
	if m["code"] == nil || m["code"] == "" {
		t.Fatal("expected code in response")
	}
}

func TestRedirect(t *testing.T) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com")

	req := httptest.NewRequest(http.MethodGet, "/abc123", nil)
	w := httptest.NewRecorder()

	h.Redirect(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusMovedPermanently {
		t.Fatalf("expected 301, got %d", resp.StatusCode)
	}
	loc := resp.Header.Get("Location")
	if loc != "https://example.com" {
		t.Fatalf("expected https://example.com, got %s", loc)
	}

	entry, _ := st.Get("abc123")
	if entry.Clicks != 1 {
		t.Fatalf("expected 1 click, got %d", entry.Clicks)
	}
}

func TestAnalytics(t *testing.T) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com")
	st.RecordClick("abc123", "1.2.3.4", "GoTest", "")

	req := httptest.NewRequest(http.MethodGet, "/analytics/abc123", nil)
	w := httptest.NewRecorder()

	h.Analytics(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusOK {
		t.Fatalf("expected 200, got %d", resp.StatusCode)
	}

	var m map[string]interface{}
	json.NewDecoder(resp.Body).Decode(&m)
	if m["total_clicks"].(float64) != 1 {
		t.Fatalf("expected 1 click, got %v", m["total_clicks"])
	}
}

func TestNotFound(t *testing.T) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	req := httptest.NewRequest(http.MethodGet, "/nonexistent", nil)
	w := httptest.NewRecorder()

	h.Redirect(w, req)

	resp := w.Result()
	if resp.StatusCode != http.StatusNotFound {
		t.Fatalf("expected 404, got %d", resp.StatusCode)
	}
}

func TestShortenDuplicate(t *testing.T) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	body := `{"url":"https://example.com/path"}`
	req1 := httptest.NewRequest(http.MethodPost, "/shorten", strings.NewReader(body))
	req1.Header.Set("Content-Type", "application/json")
	w1 := httptest.NewRecorder()
	h.Shorten(w1, req1)

	req2 := httptest.NewRequest(http.MethodPost, "/shorten", strings.NewReader(body))
	req2.Header.Set("Content-Type", "application/json")
	w2 := httptest.NewRecorder()
	h.Shorten(w2, req2)

	var m1, m2 map[string]interface{}
	json.NewDecoder(w1.Result().Body).Decode(&m1)
	json.NewDecoder(w2.Result().Body).Decode(&m2)

	if m1["code"] != m2["code"] {
		t.Fatal("duplicate URLs should return same code")
	}
}

func BenchmarkShorten(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	body := `{"url":"https://example.com/path"}`
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(http.MethodPost, "/shorten", strings.NewReader(body))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.Shorten(w, req)

		if w.Code != http.StatusCreated {
			b.Fatalf("expected 201, got %d", w.Code)
		}
	}
}

func BenchmarkRedirect(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com")
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(http.MethodGet, "/abc123", nil)
		w := httptest.NewRecorder()
		h.Redirect(w, req)
	}
}

func BenchmarkAnalytics(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com")
	st.RecordClick("abc123", "1.2.3.4", "GoBench", "")
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(http.MethodGet, "/analytics/abc123", nil)
		w := httptest.NewRecorder()
		h.Analytics(w, req)
	}
}

func BenchmarkShortenParallel(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	b.ResetTimer()
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		body := `{"url":"https://example.com/path"}`
		for pb.Next() {
			req := httptest.NewRequest(http.MethodPost, "/shorten", strings.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()
			h.Shorten(w, req)
		}
	})
}

func BenchmarkRedirectParallel(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com")
	b.ResetTimer()
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			req := httptest.NewRequest(http.MethodGet, "/abc123", nil)
			w := httptest.NewRecorder()
			h.Redirect(w, req)
		}
	})
}

func BenchmarkShortenDedupe(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	st.Set("abc123", "https://example.com/path")
	body := `{"url":"https://example.com/path"}`
	b.ResetTimer()
	b.ReportAllocs()

	for i := 0; i < b.N; i++ {
		req := httptest.NewRequest(http.MethodPost, "/shorten", bytes.NewReader([]byte(body)))
		req.Header.Set("Content-Type", "application/json")
		w := httptest.NewRecorder()
		h.Shorten(w, req)
	}
}

func BenchmarkHTTPServeRedirect(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("/shorten", h.Shorten)
	mux.HandleFunc("/analytics/", h.Analytics)
	mux.HandleFunc("/", h.Redirect)

	ts := httptest.NewServer(mux)
	defer ts.Close()

	st.Set("abc123", "https://example.com")

	b.ResetTimer()
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		client := &http.Client{
			Transport: &http.Transport{
				DisableKeepAlives: false,
				MaxConnsPerHost:   1000,
			},
		}
		for pb.Next() {
			resp, err := client.Get(ts.URL + "/abc123")
			if err != nil {
				b.Fatal(err)
			}
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
	})
}

func BenchmarkFullPipelineParallel(b *testing.B) {
	st := store.New()
	cfg := config.Load()
	h := cmd.New(st, cfg)

	mux := http.NewServeMux()
	mux.HandleFunc("/shorten", h.Shorten)
	mux.HandleFunc("/analytics/", h.Analytics)
	mux.HandleFunc("/", h.Redirect)

	ts := httptest.NewServer(mux)
	defer ts.Close()

	for i := 0; i < 1000; i++ {
		st.Set(fmt.Sprintf("code%d", i), fmt.Sprintf("https://example.com/page%d", i))
	}

	b.ResetTimer()
	b.ReportAllocs()
	b.RunParallel(func(pb *testing.PB) {
		var counter int
		client := &http.Client{
			Transport: &http.Transport{
				DisableKeepAlives: false,
				MaxConnsPerHost:   1000,
			},
		}
		for pb.Next() {
			code := fmt.Sprintf("code%d", counter%1000)
			counter++
			resp, err := client.Get(ts.URL + "/" + code)
			if err != nil {
				b.Fatal(err)
			}
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
		}
	})
}
