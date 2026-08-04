package store

import (
	"sync"
	"time"
)

type Entry struct {
	Code      string    `json:"code"`
	URL       string    `json:"url"`
	CreatedAt time.Time `json:"created_at"`
	Clicks    int64     `json:"clicks"`
}

type ClickRecord struct {
	Timestamp time.Time `json:"timestamp"`
	IP        string    `json:"ip"`
	UserAgent string    `json:"user_agent"`
	Referer   string    `json:"referer"`
}

type Store struct {
	mu      sync.RWMutex
	byCode  map[string]*Entry
	byURL   map[string]string
	clicks  map[string][]ClickRecord
	maxClicks int
}

func New() *Store {
	return &Store{
		byCode:  make(map[string]*Entry),
		byURL:   make(map[string]string),
		clicks:  make(map[string][]ClickRecord),
		maxClicks: 1000,
	}
}

func (s *Store) Set(code, url string) *Entry {
	s.mu.Lock()
	defer s.mu.Unlock()

	if existing, ok := s.byURL[url]; ok {
		return s.byCode[existing]
	}

	entry := &Entry{
		Code:      code,
		URL:       url,
		CreatedAt: time.Now().UTC(),
	}
	s.byCode[code] = entry
	s.byURL[url] = code
	return entry
}

func (s *Store) Get(code string) (*Entry, bool) {
	s.mu.RLock()
	e, ok := s.byCode[code]
	s.mu.RUnlock()
	return e, ok
}

func (s *Store) RecordClick(code, ip, userAgent, referer string) {
	s.mu.Lock()
	defer s.mu.Unlock()

	e, ok := s.byCode[code]
	if !ok {
		return
	}
	e.Clicks++

	rec := ClickRecord{
		Timestamp: time.Now().UTC(),
		IP:        ip,
		UserAgent: userAgent,
		Referer:   referer,
	}
	s.clicks[code] = append(s.clicks[code], rec)
	if len(s.clicks[code]) > s.maxClicks {
		s.clicks[code] = s.clicks[code][len(s.clicks[code])-s.maxClicks:]
	}
}

func (s *Store) Stats(code string) (*Entry, []ClickRecord, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	e, ok := s.byCode[code]
	if !ok {
		return nil, nil, false
	}

	clicks := s.clicks[code]
	out := make([]ClickRecord, len(clicks))
	copy(out, clicks)
	return e, out, true
}
