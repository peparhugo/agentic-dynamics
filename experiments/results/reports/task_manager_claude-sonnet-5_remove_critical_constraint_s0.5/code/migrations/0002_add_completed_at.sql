-- Migration 0002: track when a task was completed

ALTER TABLE tasks ADD COLUMN completed_at TEXT;
