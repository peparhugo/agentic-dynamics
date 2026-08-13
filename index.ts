"""
Codebase seed — Minimal Express Todo API (tier 1, good seams)

A single-file Express app with clean structure: models, routes, error handling.
Designed as a baseline for multi-session TypeScript stories.
"""

import express, { Request, Response } from 'express';
import sqlite3 from 'better-sqlite3';

const app = express();
app.use(express.json());

const DATABASE = process.env.DATABASE || 'todos.db';
const db = sqlite3(DATABASE);

db.exec(`
  CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL
  )
`);

// ── Models ────────────────────────────────────────────────────

interface Task {
  id: number;
  title: string;
  status: string;
  created_at: string;
}

function createTask(title: string): Task {
  const now = new Date().toISOString();
  const stmt = db.prepare(
    "INSERT INTO tasks (title, status, created_at) VALUES (?, 'pending', ?)"
  );
  const result = stmt.run(title, now);
  return { id: result.lastInsertRowid as number, title, status: 'pending', created_at: now };
}

function getTasks(): Task[] {
  return db.prepare("SELECT * FROM tasks ORDER BY created_at DESC").all() as Task[];
}

function getTask(id: number): Task | undefined {
  return db.prepare("SELECT * FROM tasks WHERE id = ?").get(id) as Task | undefined;
}

function updateTask(id: number, fields: { title?: string; status?: string }): Task | undefined {
  const task = getTask(id);
  if (!task) return undefined;
  const updates: string[] = [];
  const params: (string | number)[] = [];
  if (fields.title !== undefined) { updates.push("title = ?"); params.push(fields.title); }
  if (fields.status !== undefined) { updates.push("status = ?"); params.push(fields.status); }
  if (updates.length > 0) {
    params.push(id);
    db.prepare(`UPDATE tasks SET ${updates.join(', ')} WHERE id = ?`).run(...params);
  }
  return getTask(id);
}

// ── Routes ─────────────────────────────────────────────────────

app.get('/tasks', (_req: Request, res: Response) => {
  res.json(getTasks());
});

app.post('/tasks', (req: Request, res: Response) => {
  const title = (req.body?.title || '').trim();
  if (!title) return res.status(400).json({ error: 'title is required' });
  res.status(201).json(createTask(title));
});

app.get('/tasks/:id', (req: Request, res: Response) => {
  const task = getTask(Number(req.params.id));
  if (!task) return res.status(404).json({ error: 'task not found' });
  res.json(task);
});

app.put('/tasks/:id', (req: Request, res: Response) => {
  const task = updateTask(Number(req.params.id), {
    title: req.body?.title,
    status: req.body?.status,
  });
  if (!task) return res.status(404).json({ error: 'task not found' });
  res.json(task);
});

export default app;
