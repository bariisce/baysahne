# Architecture

## Components

```
                 ┌───────────────────────────── Audience ─────────────────────────────┐
                 │  Expo app (iOS / Android)                                          │
                 │  • public read-only API   • device registration (no account)       │
                 └──────────────┬──────────────────────────────────────▲──────────────┘
                                │ HTTPS  /api/v1/*                     │ push
                                ▼                                      │
┌──────────── Staff ───────────┐   ┌──────────────────── Backend (one codebase) ───────────────────┐
│ Browser                      │   │  api      FastAPI: public API, admin API, /legal pages, /media │
│  └─ Next.js admin panel ─────┼──▶│  worker   planner + dispatcher + receipt checker (loop)        │
│     (proxies /api, /media)   │   │                    │                         │                  │
└──────────────────────────────┘   │            PostgreSQL 16              Media storage            │
                                   │   (content, auth, jobs, audit)   (local disk or S3-compatible) │
                                   └────────────────────┬────────────────────────────────────────────┘
                                                        │ HTTPS
                                              Expo Push Service ──▶ FCM (Android) / APNs (iOS)
```

The backend is a **modular monolith**: `api` and `worker` are two process types of the same Python package and share the same database.

| Module | Responsibility |
|---|---|
| `app/models` | SQLAlchemy models (content, auth, notifications, audit) |
| `app/api/public` | Read-only audience API + device registration |
| `app/api/admin` | Authenticated admin API (auth, productions, schedule, media/articles, system) |
| `app/services` | Business logic: auth, media, visibility queries, serialisation, audit, mailer |
| `app/notifications` | Templates, providers (expo/log/fake), planning + dispatch engine, defaults |
| `app/storage` | Storage abstraction (`LocalStorage`, `S3Storage`) and image processing |
| `app/importer` | docx parser, idempotent importer, report writer |
| `app/cli.py` | `bootstrap-admin`, `import-content`, `prune` |
| `app/worker.py` | Notification worker loop |

## Key data flows

**Publishing a production.** Editor → `POST /admin/productions/{id}/publish {notify}`. This sets `status=published`. On the *first* publication, and only if `notify` is set and the category is enabled, it inserts a `new_production:{id}` job. The unique dedupe key makes a second broadcast impossible. The worker sends it, honouring the broadcast cooldown.

**Scheduling.** Staff enter venue-local wall time (`YYYY-MM-DDTHH:MM`). The server converts it to UTC with the venue's IANA timezone (default `Europe/Istanbul`) and rejects nonexistent times. Every public payload carries server-formatted Turkish local date and time fields, so the app never depends on the device clock or the phone's ICU data. Conflicts (same venue or same production within ±3 h) return `409 schedule_conflict` and need explicit confirmation.

**Reminders.** The planner runs every tick and after relevant admin actions. For each published, scheduled, future performance of a published production, and each configured lead time, it inserts `performance_reminder:{perf}:{lead}:{starts_at_epoch}`. Because the start time is part of the key, a reschedule naturally produces a new job, and the old one is cancelled as stale.

**Cancellation and reschedule.** The state change cancels pending reminders. If the performance had been announced (`first_published_at` set) and is still in the future, a single `performance_cancelled` / `performance_rescheduled:{count}` job is enqueued. Every job is re-validated immediately before sending, so a reschedule notice that is superseded by a cancellation is cancelled rather than sent.

**Media.** Upload → content-type allow-list and size limit → Pillow decodes the bytes (the claimed type is never trusted) → re-encode (metadata stripped) and generate WebP `sm` 480 px / `lg` 1280 px variants → store under random UUID keys. Rows store keys only; URLs are derived from the active storage backend at response time. Identical files are de-duplicated by SHA-256. Deletion is refused while an asset is referenced (poster, gallery, article, logo).

## Security model

- **Admin authentication.** Opaque random session token in an `httpOnly`, `SameSite=Strict` cookie (`Secure` in production). Only its SHA-256 is stored, so sessions are revocable instantly (logout, deactivation, password reset). Passwords use Argon2id. There is no public registration: accounts come from single-use, 72-hour invitations, and the first account from a CLI bootstrap that refuses to run once an admin exists.
- **Brute force.** Per-IP and per-e-mail sliding-window limits, plus a DB-backed account lockout after 5 failures (15 minutes). Login errors are identical for unknown e-mails and wrong passwords. Password-reset requests never reveal whether an account exists.
- **CSRF.** SameSite=Strict, plus a required `X-Requested-With: baysahne-admin` header on unsafe methods, plus an Origin allow-list check.
- **Authorisation** is enforced server-side per endpoint (`require_editor` / `require_admin`). The admin UI hides links for convenience only. *Editors* manage productions, performances, venues, articles and media and can view notification history. *Admins* also manage staff, notification policy and templates, the organisation profile, legal texts, the audit log, and job cancel/retry. Neither role can reach infrastructure credentials.
- **Input.** Pydantic models with `extra="forbid"`, length limits, https-only URLs, slug and enum validation, and Turkish error messages. Notification templates accept only allow-listed `{placeholders}` (no attribute or format-spec access).
- **Output.** A consistent error envelope. Unexpected exceptions are logged and returned as a generic 500. Public payloads never include internal notes, push tokens, audit data or storage credentials.
- **Headers.** `nosniff`, `DENY` framing, a strict referrer policy and HSTS when secure cookies are on. The admin panel adds a CSP. `/docs` and `/openapi.json` are disabled in production.
- **Configuration guard.** `Settings` refuses to start with `APP_ENV=production` if anything is still dev-grade (see README).

## Push provider choice

Expo Push Service is the single server integration: one HTTPS API covers FCM v1 (Android) and APNs (iOS), using credentials uploaded once to the Expo project via EAS. Firebase is used only as the FCM project behind Android delivery. Firebase Authentication and Firestore are **not** used. Swapping to direct FCM/APNs later means adding one provider class with the same `send` / `get_receipts` interface.

## Platform-specific code (mobile)

| File | Why |
|---|---|
| `src/components/app-tabs.tsx` / `.web.tsx` | Native tab bar on iOS/Android; JS tabs on web (web is used only for previews) |
| `src/lib/push.ts` | Android notification channel; push is a no-op on web and simulators |
| `app.config.ts` | Per-platform identifiers, Android permissions (POST_NOTIFICATIONS only) |
