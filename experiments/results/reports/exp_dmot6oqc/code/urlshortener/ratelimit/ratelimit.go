package ratelimit

import (
	"sync"
	"time"
)

type TokenBucket struct {
	rate       float64
	burst      int
	mu         sync.Mutex
	tokens     float64
	lastUpdate time.Time
}

func NewTokenBucket(rate float64, burst int) *TokenBucket {
	return &TokenBucket{
		rate:       rate,
		burst:      burst,
		tokens:     float64(burst),
		lastUpdate: time.Now(),
	}
}

func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastUpdate).Seconds()
	tb.tokens += elapsed * tb.rate
	if tb.tokens > float64(tb.burst) {
		tb.tokens = float64(tb.burst)
	}
	tb.lastUpdate = now

	if tb.tokens >= 1 {
		tb.tokens--
		return true
	}
	return false
}

type Limiter struct {
	mu     sync.Mutex
	rate   float64
	burst  int
	bucket map[string]*TokenBucket
}

func NewLimiter(rate float64, burst int) *Limiter {
	l := &Limiter{
		rate:   rate,
		burst:  burst,
		bucket: make(map[string]*TokenBucket),
	}
	go l.cleanup(5 * time.Minute)
	return l
}

func (l *Limiter) Allow(key string) bool {
	l.mu.Lock()
	b, ok := l.bucket[key]
	if !ok {
		b = NewTokenBucket(l.rate, l.burst)
		l.bucket[key] = b
	}
	l.mu.Unlock()
	return b.Allow()
}

func (l *Limiter) cleanup(interval time.Duration) {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for range ticker.C {
		l.mu.Lock()
		threshold := time.Now().Add(-interval)
		for k, b := range l.bucket {
			b.mu.Lock()
			last := b.lastUpdate
			b.mu.Unlock()
			if last.Before(threshold) {
				delete(l.bucket, k)
			}
		}
		l.mu.Unlock()
	}
}
