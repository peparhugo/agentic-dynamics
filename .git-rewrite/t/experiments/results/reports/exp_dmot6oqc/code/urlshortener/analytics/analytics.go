package analytics

import (
	"sync"
	"time"
)

type Click struct {
	IP        string    `json:"ip"`
	UserAgent string    `json:"user_agent"`
	Referer   string    `json:"referer"`
	Timestamp time.Time `json:"timestamp"`
}

type ClickStats struct {
	Code        string            `json:"code"`
	TotalClicks uint64            `json:"total_clicks"`
	Recent      []Click           `json:"recent,omitempty"`
	ByDay       map[string]uint64 `json:"by_day,omitempty"`
	ByReferer   map[string]uint64 `json:"by_referer,omitempty"`
}

type Tracker struct {
	mu       sync.RWMutex
	clicks   map[string][]Click
	maxClicks int
}

func NewTracker(maxClicks int) *Tracker {
	return &Tracker{
		clicks:    make(map[string][]Click),
		maxClicks: maxClicks,
	}
}

func (t *Tracker) Record(code string, ip, userAgent, referer string) {
	t.mu.Lock()
	defer t.mu.Unlock()

	click := Click{
		IP:        ip,
		UserAgent: userAgent,
		Referer:   referer,
		Timestamp: time.Now().UTC(),
	}

	clicks := t.clicks[code]
	clicks = append(clicks, click)
	if len(clicks) > t.maxClicks {
		clicks = clicks[len(clicks)-t.maxClicks:]
	}
	t.clicks[code] = clicks
}

func (t *Tracker) Stats(code string) ClickStats {
	t.mu.RLock()
	defer t.mu.RUnlock()

	clicks := t.clicks[code]
	stats := ClickStats{
		Code:        code,
		TotalClicks: uint64(len(clicks)),
		ByDay:       make(map[string]uint64),
		ByReferer:   make(map[string]uint64),
	}

	for _, c := range clicks {
		day := c.Timestamp.Format("2006-01-02")
		stats.ByDay[day]++
		if c.Referer != "" {
			stats.ByReferer[c.Referer]++
		}
	}

	if len(clicks) > 0 {
		recent := clicks
		if len(recent) > 20 {
			recent = recent[len(recent)-20:]
		}
		stats.Recent = recent
	}

	return stats
}
