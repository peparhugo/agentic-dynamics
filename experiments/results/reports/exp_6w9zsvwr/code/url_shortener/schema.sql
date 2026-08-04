CREATE TABLE IF NOT EXISTS urls (
    code TEXT PRIMARY KEY,
    url TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL REFERENCES urls(code) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT,
    ip_address TEXT
);

CREATE INDEX IF NOT EXISTS clicks_code_id ON clicks(code, id DESC);

CREATE TABLE IF NOT EXISTS rate_limits (
    client TEXT NOT NULL,
    scope TEXT NOT NULL,
    window_start INTEGER NOT NULL,
    requests INTEGER NOT NULL,
    PRIMARY KEY (client, scope, window_start)
);
