/**
 * Tier 2 Small seed — Multi-file NestJS-like Auth API (TypeScript, ~400 LOC)
 *
 * A modular Express API with JWT authentication, SQLite persistence,
 * and jest tests. Designed as a baseline for tier 2 TypeScript stories.
 */

import express, { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import sqlite3 from 'better-sqlite3';
import bcrypt from 'bcryptjs';
import { randomBytes } from 'crypto';

const app = express();
app.use(express.json());

const SECRET_KEY = process.env.SECRET_KEY || randomBytes(32).toString('hex');
const DATABASE = process.env.DATABASE || 'auth_api.db';
const TOKEN_TTL = parseInt(process.env.TOKEN_TTL || '3600', 10);

const db = sqlite3(DATABASE);

// ── Database Init ────────────────────────────────────────────────

db.exec(`
  CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TEXT NOT NULL
  );
  CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
  );
`);

// ── Types ──────────────────────────────────────────────────────

interface User {
  id: number;
  username: string;
  password_hash: string;
  role: string;
  created_at: string;
}

interface Item {
  id: number;
  user_id: number;
  name: string;
  description: string;
  created_at: string;
}

interface AuthRequest extends Request {
  user?: User;
}

// ── Auth Middleware ─────────────────────────────────────────────

function requireAuth(req: AuthRequest, res: Response, next: NextFunction): void {
  const auth = req.headers.authorization;
  if (!auth || !auth.startsWith('Bearer ')) {
    res.status(401).json({ error: 'missing authorization header' });
    return;
  }
  try {
    const token = auth.split(' ')[1];
    const payload = jwt.verify(token, SECRET_KEY) as { user_id: number };
    const user = db.prepare('SELECT * FROM users WHERE id = ?').get(payload.user_id) as User | undefined;
    if (!user) {
      res.status(401).json({ error: 'invalid token' });
      return;
    }
    req.user = user;
    next();
  } catch {
    res.status(401).json({ error: 'invalid or expired token' });
  }
}

// ── Auth Routes ─────────────────────────────────────────────────

app.post('/auth/register', (req: Request, res: Response) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    res.status(400).json({ error: 'username and password required' });
    return;
  }
  if (password.length < 8) {
    res.status(400).json({ error: 'password must be at least 8 characters' });
    return;
  }
  const existing = db.prepare('SELECT id FROM users WHERE username = ?').get(username);
  if (existing) {
    res.status(409).json({ error: 'username already taken' });
    return;
  }
  const password_hash = bcrypt.hashSync(password, 10);
  db.prepare(
    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'user', ?)"
  ).run(username, password_hash, new Date().toISOString());
  res.status(201).json({ message: 'user registered', username });
});

app.post('/auth/login', (req: Request, res: Response) => {
  const { username, password } = req.body || {};
  if (!username || !password) {
    res.status(400).json({ error: 'username and password required' });
    return;
  }
  const user = db.prepare(
    'SELECT * FROM users WHERE username = ?'
  ).get(username) as User | undefined;
  if (!user || !bcrypt.compareSync(password, user.password_hash)) {
    res.status(401).json({ error: 'invalid credentials' });
    return;
  }
  const token = jwt.sign({ user_id: user.id }, SECRET_KEY, {
    expiresIn: TOKEN_TTL,
  });
  res.json({ token, username: user.username, role: user.role });
});

// ── Item Routes ─────────────────────────────────────────────────

app.get('/items', requireAuth, (req: AuthRequest, res: Response) => {
  const items = db.prepare(
    'SELECT * FROM items WHERE user_id = ? ORDER BY created_at DESC'
  ).all(req.user!.id) as Item[];
  res.json(items);
});

app.post('/items', requireAuth, (req: AuthRequest, res: Response) => {
  const { name, description } = req.body || {};
  if (!name?.trim()) {
    res.status(400).json({ error: 'name is required' });
    return;
  }
  const now = new Date().toISOString();
  const result = db.prepare(
    'INSERT INTO items (user_id, name, description, created_at) VALUES (?, ?, ?, ?)'
  ).run(req.user!.id, name.trim(), description || '', now);
  res.status(201).json({
    id: result.lastInsertRowid,
    name: name.trim(),
    description: description || '',
    created_at: now,
  });
});

app.get('/items/:id', requireAuth, (req: AuthRequest, res: Response) => {
  const item = db.prepare(
    'SELECT * FROM items WHERE id = ? AND user_id = ?'
  ).get(Number(req.params.id), req.user!.id) as Item | undefined;
  if (!item) {
    res.status(404).json({ error: 'item not found' });
    return;
  }
  res.json(item);
});

app.delete('/items/:id', requireAuth, (req: AuthRequest, res: Response) => {
  const item = db.prepare(
    'SELECT id FROM items WHERE id = ? AND user_id = ?'
  ).get(Number(req.params.id), req.user!.id);
  if (!item) {
    res.status(404).json({ error: 'item not found' });
    return;
  }
  db.prepare('DELETE FROM items WHERE id = ?').run(Number(req.params.id));
  res.json({ message: 'item deleted' });
});

// ── Admin Routes ────────────────────────────────────────────────

app.get('/admin/users', requireAuth, (req: AuthRequest, res: Response) => {
  if (req.user!.role !== 'admin') {
    res.status(403).json({ error: 'admin access required' });
    return;
  }
  const users = db.prepare(
    'SELECT id, username, role, created_at FROM users ORDER BY created_at'
  ).all();
  res.json(users);
});

// ── Health ──────────────────────────────────────────────────────

app.get('/health', (_req: Request, res: Response) => {
  res.json({ status: 'ok' });
});

export default app;
