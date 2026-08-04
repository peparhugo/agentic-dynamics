package store

import (
	"errors"
	"sync"
	"time"
)

var ErrNotFound = errors.New("url not found")
var ErrDuplicate = errors.New("code already exists")

type URLEntry struct {
	Code      string    `json:"code"`
	URL       string    `json:"url"`
	CreatedAt time.Time `json:"created_at"`
	Clicks    uint64    `json:"clicks"`
}

type Store interface {
	Set(code, url string) (URLEntry, error)
	Get(code string) (URLEntry, error)
	Delete(code string) error
	IncrementClicks(code string)
	Exists(code string) bool
	Len() int
}

type MemoryStore struct {
	mu       sync.RWMutex
	entries  map[string]*URLEntry
	codeIdx  map[string]struct{}
	urlIdx   map[string]string
}

func NewMemoryStore() *MemoryStore {
	return &MemoryStore{
		entries: make(map[string]*URLEntry),
		codeIdx: make(map[string]struct{}),
		urlIdx:  make(map[string]string),
	}
}

func (s *MemoryStore) Set(code, url string) (URLEntry, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, exists := s.codeIdx[code]; exists {
		return URLEntry{}, ErrDuplicate
	}

	if existingCode, exists := s.urlIdx[url]; exists {
		entry := s.entries[existingCode]
		return *entry, nil
	}

	entry := &URLEntry{
		Code:      code,
		URL:       url,
		CreatedAt: time.Now().UTC(),
	}
	s.entries[code] = entry
	s.codeIdx[code] = struct{}{}
	s.urlIdx[url] = code

	return *entry, nil
}

func (s *MemoryStore) Get(code string) (URLEntry, error) {
	s.mu.RLock()
	entry, ok := s.entries[code]
	s.mu.RUnlock()

	if !ok {
		return URLEntry{}, ErrNotFound
	}
	return *entry, nil
}

func (s *MemoryStore) Delete(code string) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	entry, ok := s.entries[code]
	if !ok {
		return ErrNotFound
	}

	delete(s.urlIdx, entry.URL)
	delete(s.entries, code)
	delete(s.codeIdx, code)
	return nil
}

func (s *MemoryStore) IncrementClicks(code string) {
	s.mu.Lock()
	if entry, ok := s.entries[code]; ok {
		entry.Clicks++
	}
	s.mu.Unlock()
}

func (s *MemoryStore) Exists(code string) bool {
	s.mu.RLock()
	_, ok := s.codeIdx[code]
	s.mu.RUnlock()
	return ok
}

func (s *MemoryStore) Len() int {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return len(s.entries)
}
