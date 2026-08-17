-- 0002_add_completed_at: track task completion timestamp
ALTER TABLE tasks ADD COLUMN completed_at DATETIME;

CREATE INDEX ix_tasks_completed_at ON tasks(completed_at);
