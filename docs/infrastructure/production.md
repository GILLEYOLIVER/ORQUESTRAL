# Production readiness

## Delivery status

The production path is complete in code. External provisioning remains intentionally pending until
the database, Redis, object storage, n8n, compute, DNS, TLS, monitoring and backup providers are
authorized. No paid resource is created by this repository.

## Production architecture

- API and web images are immutable GHCR artifacts identified by the full Git commit SHA.
- PostgreSQL is managed, encrypted and backed up; the `vector` extension stores knowledge
  embeddings in the same tenant-aware database.
- Redis uses TLS and separate logical databases for cache, broker and task results.
- Object storage is private, encrypted and accessed with a dedicated least-privilege identity.
- n8n, API and background workers use private networking whenever the provider supports it.
- Public traffic terminates TLS before reaching the application. Only `/health`,
  `/ready` and the required product routes are exposed.

## GitHub protected environment

Create an environment named `production` with required reviewers, deployment branch rules
limited to `main`, and prevention of self-review. Configure:

| Type     | Name                        | Purpose                                    |
| -------- | --------------------------- | ------------------------------------------ |
| Variable | `PRODUCTION_BASE_URL`       | Canonical HTTPS application URL            |
| Secret   | `PRODUCTION_BACKUP_HOOK`    | Creates and validates a pre-change backup  |
| Secret   | `PRODUCTION_MIGRATION_HOOK` | Runs one migration task with advisory lock |
| Secret   | `PRODUCTION_DEPLOY_HOOK`    | Promotes the selected immutable SHA        |
| Secret   | `PRODUCTION_ROLLBACK_HOOK`  | Restores a selected immutable SHA          |
| Secret   | `PRODUCTION_ALERT_HOOK`     | Receives successful and failed changes     |
| Secret   | `PRODUCTION_HOOK_TOKEN`     | Dedicated bearer token, at least 32 chars  |

Provider secrets use `.env.production.example` as their key contract. Real values must
remain only in the provider secret manager. `RUN_MIGRATIONS_ON_STARTUP=false`,
`BOOTSTRAP_ENABLED=false` and `VITE_AUTH_PREVIEW_ENABLED=false` are mandatory.

## First production release

1. Protect the GitHub `production` environment and configure every variable and secret
   above.
2. Provision managed dependencies and validate encryption, private access and least privilege.
3. Restore a sanitized backup into a temporary database and prove the restore procedure.
4. Publish the selected `main` commit through `Publish images`.
5. Deploy that exact SHA to staging and retain the successful workflow URL as evidence.
6. Open `Deploy production`, select `deploy`, and provide the release SHA, last
   known-good SHA, staging evidence URL, approved change reference and
   `PROMOVER-PRODUCAO`.
7. A required reviewer approves the protected environment.
8. The workflow verifies image provenance, creates a backup, migrates once, deploys and checks
   `/system/version` plus `/ready`.
9. Confirm login, tenant isolation, asynchronous jobs, n8n, storage, billing and notifications with
   synthetic data before enabling customer traffic.

## Rollback

If post-deploy verification fails, the workflow automatically invokes the rollback hook with
`previous_sha`, verifies that release and still marks the attempted promotion as failed.

For a manual rollback, run `Deploy production` with `action=rollback` and the last
healthy SHA. The workflow creates another backup before changing the release. Database migrations
must follow the expand-and-contract pattern; destructive contraction occurs only after the rollback
window closes. If data restoration is necessary, restore into a new managed database, validate it,
then rotate `DATABASE_URL` under an approved incident change.

## Backup and recovery

- Encrypt database and object backups with provider-managed keys.
- Keep daily backups for at least 30 days and a monthly copy for 12 months.
- Target RPO is 24 hours until continuous recovery is contracted; record the provider's actual RPO.
- Target RTO is four hours; measure it with a quarterly restore exercise.
- A backup is not valid until checksum, retention and restore tests succeed.
- Keep n8n definitions, credentials and object metadata in the recovery scope.

## Observability and launch gates

Required alerts cover availability, readiness, HTTP 5xx, latency, database saturation, Redis
availability, queue depth, failed jobs, failed backups, authentication anomalies and billing
webhook failures. Logs must be structured, access-controlled and retained without token or secret
payloads.

Production traffic is allowed only when:

- CI, security audit and image scans are green for the selected SHA.
- Staging evidence references the same immutable release.
- DNS, TLS, backup restore, monitoring and alert delivery are validated.
- Database migrations are backward compatible and rollback has been rehearsed.
- A named operator owns the release and incident response window.

Run `bash scripts/check-production-readiness.sh` locally or through CI to validate the
repository contract.
