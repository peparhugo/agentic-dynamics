const Database = require('better-sqlite3');
const path = require('path');

const db = new Database(path.join(__dirname, 'urls.db'));

db.pragma('journal_mode = WAL');
db.pragma('foreign_keys = ON');

db.exec(`
  CREATE TABLE IF NOT EXISTS urls (
    code      TEXT PRIMARY KEY,
    target    TEXT NOT NULL,
    created   TEXT NOT NULL DEFAULT (datetime('now')),
    hits      INTEGER NOT NULL DEFAULT 0
  )
`);

db.exec(`
  CREATE TABLE IF NOT EXISTS clicks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL,
    clicked   TEXT NOT NULL DEFAULT (datetime('now')),
    ip        TEXT,
    referer   TEXT,
    user_agent TEXT,
    FOREIGN KEY (code) REFERENCES urls(code)
  )
`);

const insertUrl = db.prepare('INSERT INTO urls (code, target) VALUES (?, ?)');
const findByCode = db.prepare('SELECT * FROM urls WHERE code = ?');
const incrementHits = db.prepare('UPDATE urls SET hits = hits + 1 WHERE code = ?');
const insertClick = db.prepare('INSERT INTO clicks (code, ip, referer, user_agent) VALUES (?, ?, ?, ?)');
const getAllUrls = db.prepare('SELECT * FROM urls ORDER BY created DESC LIMIT 100');
const getStats = db.prepare(`
  SELECT
    u.code,
    u.target,
    u.created,
    u.hits,
    (SELECT COUNT(*) FROM clicks WHERE code = u.code) AS total_clicks,
    (SELECT COUNT(DISTINCT ip) FROM clicks WHERE code = u.code) AS unique_ips
  FROM urls u
  WHERE u.code = ?
`);

module.exports = {
  insertUrl,
  findByCode,
  incrementHits,
  insertClick,
  getAllUrls,
  getStats,
  db,
};
