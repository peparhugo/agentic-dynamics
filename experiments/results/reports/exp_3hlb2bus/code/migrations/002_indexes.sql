-- 002_indexes.sql
-- Indexes for common filter / lookup paths.

CREATE INDEX idx_tasks_creator  ON tasks (creator_id);
CREATE INDEX idx_tasks_assignee ON tasks (assignee_id);
CREATE INDEX idx_tasks_status   ON tasks (status);
CREATE INDEX idx_tasks_priority ON tasks (priority);
CREATE INDEX idx_tasks_category ON tasks (category_id);
CREATE INDEX idx_tasks_due_date ON tasks (due_date);
CREATE INDEX idx_categories_user ON categories (user_id);
