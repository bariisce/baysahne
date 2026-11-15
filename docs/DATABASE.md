# Database

PostgreSQL 16 through SQLAlchemy 2.x (sync, psycopg 3). Schema changes go **only** through Alembic (`backend/alembic/versions`). `tests/test_migrations.py` fails if the models and the migrated schema ever diverge.

Conventions:
- UUID primary keys. The append-only tables (`audit_logs`, `notification_deliveries`) use bigint.
- `created_at` / `updated_at` as `timestamptz`.
- All instants are stored in UTC. Venues carry an IANA `timezone` used for display and input.
- Enumerations are `VARCHAR` with named `CHECK` constraints, which are easy to extend in a migration.
- Constraint and index names follow a fixed naming convention (`app/db.py`).

## Entities

### Content
| Table | Purpose | Notable columns / constraints |
|---|---|---|
| `productions` | A play in the repertoire | `slug` UNIQUE, `status` draft/published/archived, `on_stage` (editorial “Sahnede” label), `is_featured`, `genres text[]`, `duration_minutes` + `act_count` + original `duration_text`, `poster_id → media_assets` (RESTRICT), `first_published_at` (drives the one-time “new production” push), `import_key` UNIQUE |
| `production_credits` | Flexible credits | `role` enum (author, director, assistant_director, translator, adaptation, poster_design, cast, other) + `role_label` for custom roles, `position` |
| `production_images` | Gallery | UNIQUE (production_id, media_id), `position`, `caption` |
| `production_videos` | Trailer / video links | https URL, `position` |
| `media_assets` | Stored files | `storage_key` UNIQUE, `sha256` UNIQUE (dedupe), dimensions, `variants` JSONB (sm/lg keys), `alt_text` |
| `venues` | Places where performances happen | `timezone` (default Europe/Istanbul), `is_active` |
| `performances` | A single dated showing | `starts_at timestamptz`, `status` scheduled/cancelled, `visibility` draft/published, `rescheduled_from`, `reschedule_count`, `first_published_at` (“announced”), `production_id`/`venue_id` RESTRICT (history is never cascaded away). Indexes: (visibility, status, starts_at), (venue_id, starts_at) |
| `articles` | Announcements / news | `status`, `published_at` (a future value schedules publication) |
| `organization_profile` | Singleton (id=1, CHECK) | contact fields, `phones text[]`, `about` JSONB, `logo_id` |
| `legal_documents` | Privacy / terms / KVKK texts | `status` (imported as draft), `applies_to` mobile_app/website/all, `review_note` |
| `import_runs` | One row per import | source SHA-256 + JSON summary |

### Auth & audit
| Table | Purpose |
|---|---|
| `admin_users` | Staff accounts: `email` UNIQUE (lower-case), `role` admin/editor, Argon2id `password_hash`, `is_active`, lockout counters |
| `admin_invitations` | Single-use invitations (`token_hash` UNIQUE, `expires_at`, `accepted_at`, `revoked_at`) |
| `admin_sessions` | Opaque session tokens (hash only), expiry, revocation, IP, user agent |
| `password_reset_tokens` | Single-use reset tokens (hash only), 60-minute expiry |
| `audit_logs` | Append-only record of admin actions (actor e-mail snapshot, action, entity, summary, JSON details, IP). Never contains passwords or tokens |

### Notifications
| Table | Purpose |
|---|---|
| `push_devices` | One row per app installation: random `installation_id` UNIQUE, Expo `push_token` UNIQUE, platform, permission, `is_active`, deactivation reason |
| `notification_category_settings` | Per category: enabled, Turkish title/body templates |
| `notification_policy` | Singleton: `reminder_lead_minutes int[]`, `max_per_device_per_day`, `broadcast_cooldown_minutes` |
| `notification_jobs` | Persistent queue: `dedupe_key` UNIQUE, status, `scheduled_for`, `next_attempt_at`, attempts/max, rendered title/body, stats, `cancel_reason`. Index (status, next_attempt_at) |
| `notification_deliveries` | One row per (job, device), UNIQUE; status ok/error/rate_limited/queued; Expo ticket id, receipt status |

## Relationships

```
productions 1─* production_credits / production_images / production_videos
productions 1─* performances *─1 venues
media_assets 1─* productions.poster / production_images / articles.image / organization_profile.logo
notification_jobs 1─* notification_deliveries *─1 push_devices
admin_users 1─* admin_sessions / password_reset_tokens ; admin_invitations → admin_users
```

## Migrations

```bash
cd backend
.venv/Scripts/alembic upgrade head
.venv/Scripts/alembic revision --autogenerate -m "describe change"
.venv/Scripts/alembic check
```

- `alembic upgrade head` applies all migrations.
- `alembic revision --autogenerate` creates a new migration. Review it before committing.
- `alembic check` verifies the models match the migrations.

The initial migration also seeds the default notification policy (24 h reminder, 3 per device per day, 60-minute broadcast cooldown) and the Turkish templates. Staff can edit all of them.

## Retention

`python -m app.cli prune --deliveries-days N --audit-days N --devices-days N --sessions-days N` deletes old delivery rows, audit entries, inactive devices, and expired sessions and reset tokens. The retention periods are a decision for the organisation (see LEGAL_REVIEW), so the command has no defaults. Schedule it (e.g. a daily cron) once the periods are agreed.
