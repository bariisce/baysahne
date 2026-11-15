# API

Base path `/api/v1`. When `APP_ENV` is not production, the full interactive OpenAPI documentation is served at `http://localhost:8100/docs` (it is disabled in production).

## Conventions

- JSON in and out. Times are ISO-8601 UTC (`starts_at`), plus server-formatted venue-local fields (`local_date`, `local_weekday`, `local_time`, `local_iso`, …) in Turkish.
- Errors always look like `{"error": {"code": "...", "message": "<Turkish user-facing text>", "details": ...}}`. Validation errors are `422` with `details.fields = [{field, message}]`. Unknown request fields are rejected.
- Collections are paginated with `page` and `page_size` (≤ 100) and return `{items, total, page, page_size}`.
- Images are `{id, url, width, height, alt, sm:{url,width,height}, lg:{…}}`. Use `sm` for lists and `lg` for full-screen views.
- Public responses carry `Cache-Control: public, max-age=30`. Admin responses are `no-store`. Media files are `immutable`.

## Public (no authentication)

| Method | Path | Notes |
|---|---|---|
| GET | `/home` | `featured` (+ `featured_source`: featured / on_stage / upcoming), `upcoming` (scheduled only), `new_productions`, `articles` |
| GET | `/productions?q&genre&has_upcoming&on_stage&page&page_size` | Published only. `q` is Turkish- and accent-insensitive |
| GET | `/productions/{slug}` | Detail: credits, gallery, videos (`youtube_id`), upcoming performances including cancelled ones (flagged) |
| GET | `/genres` | Genres used by published productions |
| GET | `/performances?production&include_cancelled&page&page_size` | Chronological upcoming schedule. Cancelled entries have `is_cancelled=true` |
| GET | `/articles`, `/articles/{slug}` | Published, `published_at <= now` |
| GET | `/organization` | Contact details + About content + logo |
| GET | `/legal`, `/legal/{slug}` | Published documents with `applies_to` mobile_app or all |
| POST | `/devices` | `{installation_id, platform: ios/android, permission, push_token?, app_version?, locale?}` → `{active}`. Idempotent per installation. Never echoes the token. Rate-limited |
| DELETE | `/devices/{installation_id}` | Stop notifications for an installation |
| GET | `/legal`, `/legal/{slug}` (no `/api` prefix) | Server-rendered HTML pages, e.g. the store privacy-policy URL |
| GET | `/media/{key}` | Local-storage mode only |

Visibility rules, enforced on the server in `services/queries.py`:
- A production is public when `status = published`.
- A performance is public when its own `visibility = published` **and** its production is public **and** `starts_at > now`.

## Admin (`/api/v1/admin`, cookie session)

Every unsafe request needs the header `X-Requested-With: baysahne-admin`. Roles: **E** = editor or admin, **A** = admin only.

| Area | Endpoints | Role |
|---|---|---|
| Auth | `POST auth/login`, `POST auth/logout`, `GET auth/me`, `POST auth/password/change`, `POST auth/password/forgot`, `POST auth/password/reset/{token}`, `GET auth/invitations/{token}`, `POST auth/invitations/{token}/accept` | public / session |
| Dashboard | `GET dashboard` | E |
| Productions | `GET/POST productions`, `GET/PATCH/DELETE productions/{id}`, `GET …/preview`, `POST …/publish {notify}`, `POST …/unpublish`, `POST …/archive`, `POST …/restore`, `PUT/DELETE …/poster`, `POST …/images`, `PUT …/images/order`, `PATCH/DELETE …/images/{image_id}` | E |
| Performances | `GET/POST performances`, `GET/PATCH/DELETE performances/{id}`, `POST …/publish`, `…/unpublish`, `…/cancel {cancellation_note, notify}`, `…/restore`, `…/reschedule {starts_at_local, notify, allow_conflict}` | E |
| Venues | `GET/POST venues`, `PUT/DELETE venues/{id}` | E |
| Media | `POST media` (multipart `file`), `GET media`, `GET/PATCH/DELETE media/{id}` (delete → 409 `media_in_use` while referenced) | E |
| Articles | `GET/POST articles`, `GET/PUT/DELETE articles/{id}`, `POST …/publish {published_at?}`, `POST …/unpublish` | E |
| Notifications | `GET notifications/settings`, `POST notifications/preview`, `GET notifications/jobs`, `GET notifications/jobs/{id}` | E |
| Notifications | `PUT notifications/categories/{category}`, `PUT notifications/policy`, `POST notifications/jobs/{id}/cancel`, `POST notifications/jobs/{id}/retry` | A |
| Staff | `GET users`, `PATCH users/{id}`, `POST users/{id}/deactivate`, `POST users/{id}/reactivate`, `POST invitations`, `POST invitations/{id}/resend`, `DELETE invitations/{id}` | A |
| Organisation / legal | `GET organization` (E), `PUT organization`, `GET legal`, `PUT legal/{id}`, `POST legal/{id}/publish`, `POST legal/{id}/unpublish` | A |
| Audit | `GET audit?action&entity_type` | A |

Notable error codes: `schedule_conflict` (409, `details.conflicts`), `use_reschedule` (409), `past_datetime`, `already_published`, `cannot_delete`, `media_in_use`, `last_admin`, `account_locked` (423), `rate_limited` (429, `details.retry_after_seconds`), `csrf_failed` (403).
