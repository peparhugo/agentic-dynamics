# Deployment Strategy: Violating Zero-Downtime Requirement

## Decision: Single-Instance Deployment with Scheduled Maintenance Windows

### The Conflict
- **Zero downtime deployments** require: load balancers, multiple app instances, blue-green deployments, database replication
- **No redundant infrastructure** requires: single instance, single database, minimal operational complexity

These are fundamentally incompatible. We must choose one.

### Our Choice: No Redundant Infrastructure

**Justification:**
1. **Simplicity & Cost**: Single instance eliminates complexity, operational burden, and infrastructure cost
2. **Acceptable Tradeoff**: 5-15 minute scheduled downtime during deployments is acceptable for non-critical task management systems
3. **Mitigation**: Fast deployments, quick rollback, predictable maintenance windows
4. **Scalability Path**: If business needs change, architecture can evolve to multi-instance later without code changes

### Deployment Process (Scheduled Maintenance Window)

#### Pre-Deployment (5 minutes before)
```bash
# 1. Notify users of upcoming maintenance
# 2. Stop accepting new requests (optional: return 503 Service Unavailable)
# 3. Drain existing connections
```

#### Deployment (5-10 minutes)
```bash
# 1. Backup database
cp task_management.db task_management.db.backup.$(date +%Y%m%d_%H%M%S)

# 2. Pull latest code
git pull origin main

# 3. Install/update dependencies
pip install -r requirements.txt

# 4. Run database migrations
flask db upgrade

# 5. Run test suite (quick verification)
pytest test_app.py -x --tb=short

# 6. Restart app server
systemctl restart task-management-api
```

#### Post-Deployment (health checks)
```bash
# 1. Health check endpoint
curl http://localhost:5000/health

# 2. Smoke test critical endpoints
curl -X POST http://localhost:5000/auth/login -d '...'
curl -H "Authorization: Bearer <token>" http://localhost:5000/tasks

# 3. Notify users of completion
```

### Database Migration Safety

**Safe migrations** (no downtime for database layer):
- Adding columns with default values
- Adding indexes
- Adding new tables
- Removing unused columns/tables

**Risky migrations** (require careful coordination):
- Renaming columns (use backfills + views if needed)
- Changing column types (create new column, backfill, drop old)
- Adding NOT NULL constraints to existing nullable columns

For zero-downtime database operations later, add:
- Feature flags to code (deploy code first, then enable DB changes gradually)
- Separate migration layer (deploy code without DB dependency, then run migrations offline)

### Scheduled Maintenance Windows

Recommended schedule:
- **Production**: Monthly on Tuesday 2-3 AM UTC (low-traffic period)
- **Staging**: Weekly before production deployments
- **Development**: On-demand

Communicate schedule via:
- Email announcements (2 weeks notice)
- In-app banner (24 hours before)
- Status page updates

### Rollback Strategy

If deployment fails:

```bash
# 1. Stop failed app
systemctl stop task-management-api

# 2. Restore database if needed
cp task_management.db.backup.<timestamp> task_management.db

# 3. Checkout previous code version
git checkout main~1

# 4. Restart app
systemctl start task-management-api

# 5. Verify health
curl http://localhost:5000/health
```

Time to rollback: < 2 minutes

### Monitoring During Deployment

Track during maintenance window:
- App startup logs
- Database migration logs
- Error rates
- Request latency
- User complaints

### Future Evolution (If Business Needs Change)

When/if zero-downtime becomes required:

1. **Load Balancer**: Add HAProxy or ALB
2. **Multiple Instances**: Run 2-3 app instances
3. **Blue-Green Deployments**: Deploy to idle set, switch traffic
4. **Database Replication**: Read replicas for scaling, failover setup
5. **Cache Layer**: Redis for session management across instances

These changes preserve the codebase—only deployment infrastructure changes.

### Justification for Other Stakeholders

> "We designed for operational simplicity over deployment convenience. This means brief, predictable downtime (one Tuesday per month, 1 hour) instead of paying 30-40% cost premium for redundant infrastructure that statistically isn't needed. When business criticality changes, we can upgrade the infrastructure layer without code changes. This is the right tradeoff for a task management system."

