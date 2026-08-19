# Task Management API

Flask and SQLite REST API for authenticated task management.

## Run

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
flask --app app:create_app run
```

Set `DATABASE` and a strong `JWT_SECRET` in production. The initial schema migration runs automatically at startup.

## API

- `POST /auth/register` with `username`, `password`
- `POST /auth/login` returns a bearer token
- `GET`, `POST /categories`
- `GET`, `POST /tasks`
- `GET`, `PATCH`, `DELETE /tasks/<id>`

Task list parameters: `page`, `per_page` (maximum 100), `search`, `status`, `priority`, and `category_id`.

## Deployment Tradeoff

This implementation prioritizes **zero-downtime deployments** over the no-redundant-infrastructure constraint. Run multiple stateless application instances behind a load balancer while applying backward-compatible, additive migrations before the application rollout. That necessarily duplicates application capacity, but prevents requests from being interrupted during deploys. SQLite itself is suitable for a single-node deployment; production multi-instance zero-downtime operation should use a shared transactional database such as PostgreSQL.
