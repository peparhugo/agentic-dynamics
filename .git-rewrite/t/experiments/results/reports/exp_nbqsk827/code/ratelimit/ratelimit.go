package ratelimit

import (
	"net/http"
	"sync"
	"time"
)

type TokenBucket struct {
	rate   float64
	burst  float64
	tokens float64
	last   time.Time
}

type Limiter struct {
	mu      sync.Mutex
	buckets map[string]*TokenBucket
	rate    float64
	burst   float64
}

func NewLimiter(rps, burst int) *Limiter {
	l := &Limiter{
		buckets: make(map[string]*TokenBucket),
		rate:    float64(rps),
		burst:   float64(burst),
	}
	go l.cleanup(5 * time.Minute)
	return l
}

func (l *Limiter) Allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()

	b, ok := l.buckets[key]
	if !ok {
		b = &TokenBucket{
			rate:  l.rate,
			burst: l.burst,
			tokens: l.burst,
			last:  time.Now(),
		}
		l.buckets[key] = b
	}

	now := time.Now()
	elapsed := now.Sub(b.last).Seconds()
	b.tokens += elapsed * b.rate
	if b.tokens > b.burst {
		b.tokens = b.burst
	}
	b.last = now

	if b.tokens >= 1 {
		b.tokens--
		return true
	}
	return false
}

func (l *Limiter) cleanup(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()
	for range ticker.C {
		l.mu.Lock()
		cutoff := time.Now().Add(-15 * time.Minute)
		for k, b := range l.buckets {
			if b.last.Before(cutoff) {
				delete(l.buckets, k)
			}
		}
		l.mu.Unlock()
	}
}

func Middleware(l *Limiter) func(http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			key := r.Header.Get("X-Forwarded-For")
			if key == "" {
				key = r.RemoteAddr
			}
			if !l.Allow(key) {
				http.Error(w, `{"error":"rate limit exceeded"}`, http.StatusTooManyRequests)
				return
			}
			next.ServeHTTP(w, r)
		})
	}
}
