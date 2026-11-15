# Bay Sahne — Implementation Plan

Status legend: ☐ not started · ◐ in progress · ☑ done (verified by tests or live run)

## 1. Starting point (inspected 2026-10-16)

- The workspace had no code and no git repository. It contained only `BAY SAHNE BİLGİLER.docx` and 92 media files.
- Every media file has an `.svg` extension, but none of them are SVG. Magic-byte inspection found 88 JPEG, 3 WebP (`frankesteinbaysahne`, `lysistratabaysahne`, `bygrpic12`) and 1 PNG (`baysahnelogo1`, 5000×5000 RGBA). The importer therefore detects the real type from the bytes and never trusts the extension.
- Referenced in the document but **absent**: `r&jpic2.svg` … `r&jpic11.svg` (10 Romeo ve Juliet photographs).
- Present but **not referenced** in the document: `baysahnelogo1.svg` (current wordmark, used on baysahne.com) and `baysahnelogo2.svg` (older hat-and-suit logo).
- Official branding was taken from the live site https://www.baysahne.com: background `#0C0A09`, text `#F5F0E8`, gold accent `#C4973F`, muted `#9C8B72` / `#6B5B46`, typefaces Playfair Display (display) and Inter (text). These are used as design tokens. No colours or logos were invented.
- Local toolchain: Python 3.13/3.14, Node 24, Docker 28, PostgreSQL 16 (host install, credentials unknown → the project uses its own Postgres container on port 5433).

## 2. Architecture (summary — details in ARCHITECTURE.md)

```
mobile/  Expo (SDK 58) + Expo Router + TypeScript   ──HTTPS──▶  backend/  FastAPI modular monolith
admin/   Next.js (App Router) + TypeScript          ──/api──▶             ├─ PostgreSQL (SQLAlchemy 2 + Alembic)
                                                                           ├─ Media storage (local FS | S3-compatible)
                                                    worker process ◀──────┤─ Notification jobs (DB-backed queue)
                                                       └──▶ Expo Push Service ──▶ FCM / APNs
```

- **One backend, two process types:** `api` (HTTP) and `worker` (notification planner and dispatcher). Both share the same code and database.
- **Admin auth:** opaque session token in an httpOnly, `SameSite=Strict` cookie. Only the token's hash is stored in the DB. The admin panel proxies `/api/*` to the backend, so the cookie is first-party. A CSRF header is required on unsafe methods. Passwords are hashed with Argon2id. There is no public registration: accounts are created by invitation only, and the first account comes from a one-time CLI bootstrap.
- **Roles:** `admin` manages staff, notification settings, legal texts, organization profile and the audit log, plus everything an editor can do. `editor` manages productions, performances, venues, articles and media. Infrastructure secrets are never reachable from either role.
- **Push:** Expo Push Service over HTTP (Expo handles FCM v1 and APNs credentials). Providers are pluggable: `expo` (real), `log` (dev: records and simulates) and `fake` (tests).
- **Scheduling:** persistent `notification_jobs` with a unique `dedupe_key`. They are claimed with `FOR UPDATE SKIP LOCKED`, and each device gets a unique `(job, device)` delivery row. Restarts and retries therefore cannot double-send.

## 3. Data model (details in DATABASE.md)

`productions`, `production_credits`, `production_images`, `production_videos`, `media_assets`, `venues`, `performances`, `articles`, `organization_profile`, `legal_documents`, `admin_users`, `admin_invitations`, `admin_sessions`, `password_reset_tokens`, `push_devices`, `notification_category_settings`, `notification_policy`, `notification_jobs`, `notification_deliveries`, `audit_logs`, `import_runs`.

Key separations required by the brief:
- Production **publication status** (`draft` / `published` / `archived`) is independent of the **schedule**. A published production with no performances is valid.
- The `on_stage` flag ("Sahnede") comes from the "SAHNEDEKİ OYUNLAR" section as import metadata only. It is editable and is not treated as proof of real-world availability.
- A performance has a **visibility** (`draft` / `published`) and a **lifecycle** (`scheduled` / `cancelled`), plus reschedule tracking (`rescheduled_from`, `reschedule_count`).

## 4. Milestones

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Repo structure, Docker Compose, env config, .gitignore, CI workflow | ☑ |
| 2 | SQLAlchemy models + Alembic migration | ☑ |
| 3 | Public API, admin API, auth (invite / accept / login / logout / reset / revoke), RBAC, audit, rate limits | ☑ |
| 4 | Idempotent content importer for the docx and media + `CONTENT_IMPORT_REPORT.md` | ☑ |
| 5 | Notification system: device registration, settings, job planner, dispatcher, receipts, dev provider | ☑ |
| 6 | Admin panel (Next.js): login / invite / reset, dashboard, productions, media, performances, venues, articles, notifications, staff, settings, audit | ☑ |
| 7 | Mobile app (Expo): home, catalog, detail, schedule, news, about, legal, push registration | ☑ |
| 8 | End-to-end verification, security review, documentation, release prep | ◐ (done in code and docs; real accounts and store submission pending) |

## 5. Key decisions

| Decision | Choice | Why |
|---|---|---|
| ORM mode | SQLAlchemy 2 **sync** + psycopg 3 | Simple and well-tested. FastAPI runs sync endpoints in a threadpool, which is plenty for one theatre's traffic. |
| Password hash | Argon2id (`argon2-cffi`) | Current OWASP recommendation. |
| Sessions vs JWT | DB-backed opaque sessions | Instant revocation (staff removal), no token-signing key to manage. |
| Push | Expo Push Service | One server integration covers FCM v1 + APNs; credentials are uploaded once to EAS. Firebase is used only as the FCM project behind Android. |
| Media variants | Pillow re-encode to WebP (`sm` 480 px, `lg` 1280 px) plus the original | Sensible mobile sizes. Re-encoding also strips EXIF and neutralises malformed files. |
| Rate limiting | In-process sliding window **plus** DB account lockout | Lockout survives restarts. The in-process limiter is documented as per-instance. |
| Legal texts | Imported verbatim as **draft** `legal_documents`; nothing published automatically | The source texts describe a website with membership, comments and Firebase Auth/Firestore, none of which exist here (see LEGAL_REVIEW.md). |
| App identifiers | Read from env (`APP_IOS_BUNDLE_ID`, `APP_ANDROID_PACKAGE`); production builds fail fast if they are unset | The brief forbids inventing permanent identifiers. |
| Timezone | Store `timestamptz` (UTC); each venue has a `timezone` (default `Europe/Istanbul`); display converts to it | Correct across DST rule changes. |

## 6. Verification strategy

- **Backend:** pytest against an isolated Postgres database (`baysahne_test`), with migrations applied by Alembic in the test session. Covers visibility, ordering, cancel/reschedule, auth/RBAC, CRUD, media, devices, notification planning, duplicate prevention and audit.
- **Importer:** run twice; assert identical counts and no duplicates (test plus live run).
- **Admin:** Vitest + Testing Library for forms, validation, access and error states; live browser drive of the full workflow.
- **Mobile:** jest-expo + React Native Testing Library for screens, empty states, API client and push registration; Expo web build driven in the browser pane for visual verification.
- **E2E:** the 10-step workflow from the brief, scripted against the running stack with the `log` push provider.

## 7. Progress log

### 2026-10-16 — first full build (all milestones implemented, nothing committed)

**Verified by execution:**
- Backend: **71 pytest tests pass** against an isolated `baysahne_test` Postgres database, and `ruff` is clean. Coverage: visibility rules, ordering, cancel/reschedule, auth/RBAC/lockout/rate limits/CSRF, invitation and reset flows, CRUD, media validation/dedupe/in-use protection, device registration, every notification guarantee (dedupe, at-most-once, retries/backoff, stuck recovery, receipts, frequency cap, cooldown, stale-job cancellation), audit entries, migration ↔ model parity, the importer (idempotency), S3 storage (moto), retention pruning, and the brief's 10-step workflow.
- Admin: 16 Vitest tests, ESLint, `tsc` and `next build` all pass.
- Mobile: 14 Jest tests, ESLint, `tsc` and `expo-doctor` (20/20) all pass.
- Import: run twice on the real docx (17 records and 91 images on the first run, 0 new on the second); report in `CONTENT_IMPORT_REPORT.md`.
- **Live walk-through of the 10-step workflow**:
  - Admin invited an editor through the panel; the invitation link was accepted in the browser.
  - The editor created a production, uploaded a poster through the real multipart path, and published it with notify.
  - The production appeared in the Expo web build.
  - The editor created a performance (22 Oct 20:30, Europe/Istanbul), which appeared in the app schedule.
  - The worker sent the new-production push once to 2 simulated devices (log provider); a second run sent nothing.
  - Cancelling in the UI cancelled the pending 24 h reminder and sent the cancellation notice exactly once; the app shows “İPTAL EDİLDİ”.
  - The editor got 403 on admin-only endpoints.
- Docker images for `api` and `admin` build and pass a smoke test: `/healthz`, public API, admin `/giris`, admin → API proxy, CSP header.

**Changes made after verification:**
- Venue pre-selection race in the performance form.
- Images blocked by the admin CSP (`MEDIA_PUBLIC_ORIGIN`).
- Bootstrap CLI now validates e-mail like the login form does.
- Invitation and reset tokens moved from URL paths to the URL fragment plus request body, so they never reach access logs.
- `Link asChild` style function dropped on web.
- Admin Docker image: the backend URL is now a build arg, because Next.js bakes rewrites in at build time (found by a container smoke test: `/api` proxy returned 500, 200 after the fix). The production-config guard was also verified inside the API image: `APP_ENV=production` with dev settings refuses to start.

**Not verified / requires your accounts or decisions:**
- Real push delivery to physical iOS/Android devices (needs EAS project, FCM and APNs credentials). The Expo provider code path is implemented but has only been exercised with the log and fake providers.
- SMTP delivery (needs an SMTP provider).
- Native builds (`eas build`) and store submission.
- Production hosting and managed Postgres / S3 provider choice (billable — needs your approval).
- Final app identifiers, staff list, legal texts (see LEGAL_REVIEW.md) and the retention periods.
