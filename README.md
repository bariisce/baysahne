# Bay Sahne

Turkish-language mobile app, admin panel and API for **Baysahne Performans Atölyesi** (Adana). Audiences can browse productions, read about each play, see posters and photographs, watch trailers and check performance dates. Staff manage all of that content in a secure web panel. The backend sends push notifications for new productions, upcoming performances and schedule changes.

| Part | Path | Stack |
|---|---|---|
| API + notification worker | [`backend/`](backend) | Python 3.13, FastAPI, SQLAlchemy 2, Alembic, PostgreSQL 16 |
| Admin panel | [`admin/`](admin) | Next.js 16 (App Router), React 19, TypeScript |
| Audience app | [`mobile/`](mobile) | Expo SDK 58, Expo Router, React Native 0.88, TypeScript |
| Source content | repository root | `BAY SAHNE BİLGİLER.docx` + supplied media (`*.svg`, which are really JPEG/PNG/WebP) |

Out of scope for v1 (by design): ticket sales, payments, seat maps, QR tickets, user accounts, reviews and recommendations.

## Documentation

| Document | Contents |
|---|---|
| [IMPLEMENTATION_PLAN](docs/IMPLEMENTATION_PLAN.md) | Milestones, decisions, progress |
| [ARCHITECTURE](docs/ARCHITECTURE.md) | Components, data flows, security model |
| [DATABASE](docs/DATABASE.md) | Entities, relationships, migrations |
| [API](docs/API.md) | Endpoint overview (live OpenAPI at `/docs` outside production) |
| [ADMIN_GUIDE](docs/ADMIN_GUIDE.md) | First admin bootstrap, inviting staff, everyday content work (includes a Turkish staff guide) |
| [NOTIFICATIONS](docs/NOTIFICATIONS.md) | Device registration, scheduling, FCM/APNs setup, troubleshooting |
| [DEPLOYMENT](docs/DEPLOYMENT.md) | Hosting, environment variables, backups, release procedure |
| [APP_STORE_RELEASE](docs/APP_STORE_RELEASE.md) | App Store / Google Play preparation |
| [LEGAL_REVIEW](docs/LEGAL_REVIEW.md) | Privacy/KVKK questions that need the organisation's (and a lawyer's) decision |
| [CONTENT_IMPORT_REPORT](docs/CONTENT_IMPORT_REPORT.md) | What was imported from the docx, missing assets, inconsistencies |

## Prerequisites

- Docker (for PostgreSQL; the whole stack can also run in containers)
- Python 3.13 (3.12+ works)
- Node.js 24 + npm
- For device testing: Expo Go is **not** enough for push notifications; use a development build (see APP_STORE_RELEASE).

## Local setup

```bash
cp .env.example .env
```

Edit `.env` and set your own local values. The development defaults work with the compose database. Next, start PostgreSQL. It creates both the `baysahne` and `baysahne_test` databases.

```bash
docker compose up -d db
```

The database container restarts by itself whenever Docker starts, but Docker Desktop has to be running. If the app or the admin panel answers "Hizmet geçici olarak kullanılamıyor" (HTTP 503) and the API log says `Database unavailable`, the database is not reachable: start Docker Desktop and the API recovers on the next request, with no restart needed.

Set up the backend:

```bash
cd backend
python -m venv .venv
.venv/Scripts/pip install -e ".[dev]"
.venv/Scripts/alembic upgrade head
.venv/Scripts/python -m app.cli import-content
.venv/Scripts/python -m app.cli bootstrap-admin --email you@example.com --name "Ad Soyad"
```

(On macOS/Linux use `.venv/bin/` instead of `.venv/Scripts/`.)

- `import-content` is idempotent and regenerates `docs/CONTENT_IMPORT_REPORT.md`.
- `bootstrap-admin` prints a one-time invitation link for the **first** administrator. Open it to set a password.

Run the API on :8100 and the notification worker (separate terminals):

```bash
.venv/Scripts/python -m uvicorn app.main:app --port 8100
```

```bash
.venv/Scripts/python -m app.worker
```

Admin panel on http://localhost:3100. It proxies `/api` and `/media` to the API.

```bash
cd admin && npm install && npm run dev
```

Mobile app: press `i` / `a` for a simulator, or `w` for a browser preview.

```bash
cd mobile && npm install && npx expo start
```

On a physical phone on the same network, no addresses need configuring: start the API with `--host 0.0.0.0` so the phone can reach it, and leave `API_URL` and `PUBLIC_API_BASE_URL` unset. In development the app calls the API on the computer it loaded the bundle from, and the API builds media URLs from the address each request came in on. This keeps working when the computer's IP changes (another Wi-Fi network, a phone hotspot): after a change, restart `npx expo start` and scan the new QR code, nothing else. Do not prefix the API command with `PUBLIC_API_BASE_URL=http://<ip>:8100`; in development the API ignores it for requests and logs a warning, because a fixed address goes stale on the next network. Set `API_URL` only to point the app at a different server.

Everything in containers (API, worker, admin):

```bash
docker compose --profile full up -d --build
```

## Common commands

| Task | Command |
|---|---|
| Backend tests (isolated `baysahne_test` DB) | `cd backend && .venv/Scripts/python -m pytest` |
| Backend lint | `cd backend && .venv/Scripts/ruff check app tests` |
| New migration | `cd backend && .venv/Scripts/alembic revision --autogenerate -m "..."` |
| Run worker once | `cd backend && .venv/Scripts/python -m app.worker --once` |
| Retention cleanup | `python -m app.cli prune --deliveries-days N --audit-days N --devices-days N --sessions-days N` |
| Admin lint / types / tests / build | `cd admin && npm run lint && npm run typecheck && npm test && npm run build` |
| Mobile lint / types / tests | `cd mobile && npx eslint . && npx tsc --noEmit && npx jest` |
| Mobile health check | `cd mobile && npx expo-doctor` |

CI runs all of these: [.github/workflows/ci.yml](.github/workflows/ci.yml).

## Development safety

- `PUSH_PROVIDER=log` (default) records notifications in the worker log and DB and never contacts a push service. Tests use an in-memory fake provider.
- `EMAIL_BACKEND=console|file` prints or writes invitation and reset e-mails locally. Both are refused when `APP_ENV=production`.
- Production startup fails if it detects development-grade settings: non-HTTPS URLs, insecure cookies, a non-SMTP mailer, the log push provider, or the dev database password.
- Real secrets live only in `.env` / your secrets manager. `.env*` files, keystores, `google-services.json` and Apple keys are git-ignored.
