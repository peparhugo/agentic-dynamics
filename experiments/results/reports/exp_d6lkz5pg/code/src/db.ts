import Database from "better-sqlite3";
import path from "node:path";

const DB_PATH = path.join(import.meta.dirname, "..", "shortener.db");

const db = new Database(DB_PATH);

db.pragma("journal_mode = WAL");
db.pragma("foreign_keys = ON");

db.exec(`
  CREATE TABLE IF NOT EXISTS urls (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT NOT NULL UNIQUE,
    original_url TEXT NOT NULL,
    created_at INTEGER NOT NULL DEFAULT (unixepoch()),
    expires_at INTEGER
  );

  CREATE INDEX IF NOT EXISTS idx_urls_short_code ON urls(short_code);
  CREATE INDEX IF NOT EXISTS idx_urls_expires_at ON urls(expires_at);

  CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT NOT NULL,
    clicked_at INTEGER NOT NULL DEFAULT (unixepoch()),
    ip TEXT,
    user_agent TEXT,
    referer TEXT,
    FOREIGN KEY (short_code) REFERENCES urls(short_code) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_clicks_short_code ON clicks(short_code);
  CREATE INDEX IF NOT EXISTS idx_clicks_clicked_at ON clicks(clicked_at);
`);

const insertUrlStmt = db.prepare(
  "INSERT INTO urls (short_code, original_url, expires_at) VALUES (?, ?, ?)"
);

const findByCodeStmt = db.prepare(
  "SELECT * FROM urls WHERE short_code = ? AND (expires_at IS NULL OR expires_at > unixepoch())"
);

const insertClickStmt = db.prepare(
  "INSERT INTO clicks (short_code, ip, user_agent, referer) VALUES (?, ?, ?, ?)"
);

const countClicksStmt = db.prepare(
  "SELECT COUNT(*) as total FROM clicks WHERE short_code = ?"
);

const clicksOverTimeStmt = db.prepare(`
  SELECT date(datetime(clicked_at, 'unixepoch')) as day, COUNT(*) as count
  FROM clicks
  WHERE short_code = ?
  GROUP BY day
  ORDER BY day DESC
  LIMIT ? OFFSET ?
`);

const recentClicksStmt = db.prepare(`
  SELECT * FROM clicks WHERE short_code = ? ORDER BY clicked_at DESC LIMIT ? OFFSET ?
`);

const countUrlsStmt = db.prepare("SELECT COUNT(*) as total FROM urls");
const countAllClicksStmt = db.prepare("SELECT COUNT(*) as total FROM clicks");

export interface URLRecord {
  id: number;
  short_code: string;
  original_url: string;
  created_at: number;
  expires_at: number | null;
}

export interface ClickRecord {
  id: number;
  short_code: string;
  clicked_at: number;
  ip: string | null;
  user_agent: string | null;
  referer: string | null;
}

export function insertUrl(short_code: string, original_url: string, expires_at: number | null): void {
  insertUrlStmt.run(short_code, original_url, expires_at);
}

export function getByCode(short_code: string): URLRecord | undefined {
  return findByCodeStmt.get(short_code) as URLRecord | undefined;
}

export function recordClick(short_code: string, ip: string | null, user_agent: string | null, referer: string | null): void {
  insertClickStmt.run(short_code, ip, user_agent, referer);
}

export function getClickCount(short_code: string): number {
  const row = countClicksStmt.get(short_code) as { total: number };
  return row.total;
}

export function getClicksOverTime(short_code: string, limit: number = 30, offset: number = 0): { day: string; count: number }[] {
  return clicksOverTimeStmt.all(short_code, limit, offset) as { day: string; count: number }[];
}

export function getRecentClicks(short_code: string, limit: number = 50, offset: number = 0): ClickRecord[] {
  return recentClicksStmt.all(short_code, limit, offset) as ClickRecord[];
}

export function getStats(): { totalUrls: number; totalClicks: number } {
  const urls = countUrlsStmt.get() as { total: number };
  const clicks = countAllClicksStmt.get() as { total: number };
  return { totalUrls: urls.total, totalClicks: clicks.total };
}

export function deleteExpired(): number {
  const result = db.prepare("DELETE FROM urls WHERE expires_at IS NOT NULL AND expires_at <= unixepoch()").run();
  return result.changes;
}

export default db;
