package config

import (
	"os"
	"strconv"
	"time"
)

type Config struct {
	Port            string
	BaseURL         string
	CodeLength      int
	MaxURLBytes     int
	RateLimitRPS    int
	RateLimitBurst  int
	ReadTimeout     time.Duration
	WriteTimeout    time.Duration
	ShutdownTimeout time.Duration
}

func Load() *Config {
	return &Config{
		Port:            envStr("PORT", "8080"),
		BaseURL:         envStr("BASE_URL", "http://localhost:8080"),
		CodeLength:      envInt("CODE_LENGTH", 7),
		MaxURLBytes:     envInt("MAX_URL_BYTES", 2048),
		RateLimitRPS:    envInt("RATE_LIMIT_RPS", 100),
		RateLimitBurst:  envInt("RATE_LIMIT_BURST", 200),
		ReadTimeout:     envDuration("READ_TIMEOUT", 5*time.Second),
		WriteTimeout:    envDuration("WRITE_TIMEOUT", 10*time.Second),
		ShutdownTimeout: envDuration("SHUTDOWN_TIMEOUT", 10*time.Second),
	}
}

func envStr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			return n
		}
	}
	return def
}

func envDuration(key string, def time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		if d, err := time.ParseDuration(v); err == nil {
			return d
		}
	}
	return def
}
