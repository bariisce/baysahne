# Deployment

Nothing has been deployed and no paid resource has been created. Every step below that creates a billable resource needs your decision first.

## Target topology (single small VM or container host is enough for v1)

| Process | Image | Notes |
|---|---|---|
| `api` | `backend/Dockerfile` | `uvicorn app.main:app`; run `alembic upgrade head` before starting a new version |
| `worker` | same image, `python -m app.worker` | Exactly one is enough; more are safe (SKIP LOCKED) |
| `admin` | `admin/Dockerfile` | Next.js standalone; build arg `BACKEND_INTERNAL_URL=http://api:8100` |
| PostgreSQL 16 | managed service recommended | Daily backups + point-in-time recovery |
| Media | S3-compatible bucket (`MEDIA_STORAGE=s3`) or a persistent volume (`local`) | Public-read via CDN/bucket URL; writes only from the API |
| TLS reverse proxy | Caddy / Nginx / platform load balancer | HTTPS for `api.<domain>` and `admin.<domain>` |

Suggested hostnames (placeholders; choose your own):
- `https://api.<your-domain>` serves the mobile app API, `/legal/*` and `/media/*` (local mode).
- `https://yonetim.<your-domain>` serves the admin panel.

Production CORS must contain **only** the admin origin. The mobile app is native and does not need CORS.

## Environment variables (backend)

See `.env.example` for the full list. Production requirements are enforced at startup:

| Variable | Production value |
|---|---|
| `APP_ENV` | `production` |
| `DATABASE_URL` | managed Postgres URL (TLS) — secret |
| `PUBLIC_API_BASE_URL` | `https://api.<domain>` |
| `ADMIN_BASE_URL` | `https://yonetim.<domain>` (used in invitation and reset links) |
| `CORS_ALLOWED_ORIGINS` | `https://yonetim.<domain>` |
| `COOKIE_SECURE` | `true` |
| `EMAIL_BACKEND` | `smtp` + `SMTP_HOST/PORT/USERNAME/PASSWORD`, `EMAIL_FROM` — secrets |
| `PUSH_PROVIDER` | `expo` (+ optional `EXPO_ACCESS_TOKEN` secret) |
| `MEDIA_STORAGE` | `s3` + `S3_BUCKET`, `S3_REGION`, `S3_ENDPOINT_URL` (non-AWS), `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` (secrets), `S3_PUBLIC_BASE_URL` |
| `FORWARDED_ALLOW_IPS` | IP of your reverse proxy (so rate limits and audit see real client IPs) |

Admin image build args: `BACKEND_INTERNAL_URL` (where `/api` and `/media` are proxied, e.g. `http://api:8100`) and `MEDIA_PUBLIC_ORIGIN` (e.g. `https://cdn.<domain>`, added to the CSP `img-src`). Both are baked in at build time because Next.js resolves rewrites and headers during `next build`, so rebuild the image if they change.

Store secrets in the platform's secret manager, never in the repository or images.

## Release procedure

1. CI is green (backend tests against Postgres, admin lint/test/build, mobile lint/types/tests).
2. Back up the database.
3. Build and push images, tagged with the git SHA.
4. Run `alembic upgrade head` (one-off job using the new image).
5. Roll the `api`, `worker` and `admin` processes.
6. Smoke test:
   - `GET /healthz`
   - `GET /api/v1/home`
   - admin login
   - **Bildirimler** shows “Gerçek gönderim”
7. First deployment only:
   - `python -m app.cli import-content --source <copy of the repository's content/ folder>` (the backend image does not contain `content/`; mount or copy it for this one run)
   - `python -m app.cli bootstrap-admin --email <you> --name "<name>"`

Rollback: redeploy the previous image tag. Migrations are additive in v1; if a future migration is destructive, document its downgrade before release.

## Backups and retention

- Database: provider-managed daily snapshots plus PITR (≥ 7 days). Test a restore before launch.
- Media bucket: enable versioning, or replicate the bucket.
- Operational data retention: schedule `python -m app.cli prune …` once the organisation decides the periods (LEGAL_REVIEW §4).

## Monitoring (minimum)

- Uptime check on `/healthz`.
- Alert on worker log lines `push provider unavailable` and `worker tick failed`, and on the count of `failed` notification jobs (also shown on the admin dashboard).
- Postgres disk and connection metrics from the provider.

## Scaling notes

- The in-process login rate limiter is per API instance. With more than one instance, add an edge rate limit (proxy/WAF). The DB-backed account lockout still applies.
- Local media storage requires a single API instance with a persistent volume. Use S3 when scaling out.

## S3-compatible storage

`MEDIA_STORAGE=s3` works with AWS S3, Cloudflare R2, Backblaze B2, Hetzner Object Storage, etc. (`S3_ENDPOINT_URL` for non-AWS). Objects are written with `Cache-Control: public, max-age=31536000, immutable` and served from `S3_PUBLIC_BASE_URL` (bucket public-read or behind a CDN). The bucket credentials are used only by the API, never by the browser or app.

Verified by `backend/tests/test_s3_storage.py` against moto's in-process S3 emulator: upload, variants, content types, cache headers, URL derivation and deletion. Run one manual upload against the real provider once it is chosen.

To move existing local media to S3, copy `backend/var/media/*` (or the media volume) to the bucket, keeping the same keys, then switch `MEDIA_STORAGE`. No database change is needed because rows store keys, not URLs.
