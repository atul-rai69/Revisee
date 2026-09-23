# Revisee production deployment

This runbook prepares the Angular frontend for Vercel and the FastAPI backend
for Render native Python. Production deploys originate from the GitHub `main`
branch. Never commit `.env` files or paste secret values into this document.

## Pre-deployment gates

1. Create a Neon restore point or confirm the current branch/backup recovery
   procedure. Record the restore point time and owner outside this repository.
2. From `backend/`, run `python scripts/deployment_readiness.py`. It is
   read-only and fails if Alembic is behind the repository head or required
   tables/columns are missing.
3. Review pending migrations with `python -m alembic current` and
   `python -m alembic heads`. Apply migrations only after separate approval.
4. Run backend tests against an explicitly configured disposable PostgreSQL
   database. Never point `TEST_DATABASE_URL` at Neon production.
5. Run `npm test -- --watch=false`, `npx tsc -p tsconfig.app.json --noEmit`,
   and a production build from `frontend/`.

## Render backend

- Blueprint: `render.yaml` at the repository root.
- Root directory: `backend`.
- Runtime: native Python 3.11.9.
- Build command: `pip install -r requirements.txt`.
- Start command: `uvicorn src.main:app --host 0.0.0.0 --port $PORT`.
- Health check: `/health`.
- Branch: `main`.
- Automatic deployment is intentionally disabled for the first release.

Populate every `sync: false` variable in the Render dashboard. Use the Neon
pooled application connection string if that is the approved application URL.
Keep a direct/unpooled Neon URL available only for controlled migration work if
Neon's current guidance requires it.

`BYOK_ENCRYPTION_KEYS` must contain the existing key versions whenever stored
AI credentials exist. `BYOK_ACTIVE_ENCRYPTION_KEY_VERSION` must name a key in
that same keyring. Replacing the keyring with a new key alone makes existing
credentials unreadable. Add a new version for rotation and retain older keys
until all stored credentials have been re-encrypted or deleted.

Set `CORS_ORIGINS` as a JSON array of exact HTTPS origins, for example the
stable Vercel production domain and an approved custom domain. Production
configuration rejects wildcard, HTTP, localhost, paths, queries, and fragments.

Do not configure `TEST_DATABASE_URL` on the production service. Do not add an
automatic migration command to application startup.

### Render environment inventory

The following names come from `src.core.config.Settings` unless marked as a
Render platform variable.

Required deployment-specific values:

- `DATABASE_URL`
- `SECRET_KEY` (at least 32 characters; use a production-only random value)
- `GOOGLE_API_KEY`
- `CLOUDINARY_CLOUD_NAME`
- `CLOUDINARY_API_KEY`
- `CLOUDINARY_API_SECRET`
- `CORS_ORIGINS` (JSON array of exact production HTTPS origins)
- `BYOK_ACTIVE_ENCRYPTION_KEY_VERSION` and `BYOK_ENCRYPTION_KEYS` together.
  They are required for this database because encrypted credentials exist.

Production controls and defaults represented in `render.yaml`:

- `ENVIRONMENT`, `REVISEE_DEBUG` (or the supported alias `APP_DEBUG`)
- `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `SESSION_EXPIRE_MINUTES`
- `GEMINI_MODEL`, `AI_GENERATION_ENABLED`
- `AI_MAX_SOURCE_CHARACTERS`, `AI_MAX_THEORY_CHARACTERS`
- `AI_MAX_KEY_POINT_CHARACTERS`, `AI_MAX_NOTES_CHARACTERS`
- `AI_MAX_PROMPT_CHARACTERS`, `AI_MAX_RAW_RESPONSE_CHARACTERS`
- `AI_MAX_OUTPUT_TOKENS`, `AI_MAX_QUESTIONS_PER_CALL`
- `AI_MAX_SOURCE_ITEMS_PER_OPERATION`, `AI_PROVIDER_TIMEOUT_SECONDS`
- `AI_OPERATION_DEADLINE_SECONDS`, `AI_PROVIDER_ATTEMPTS`
- `AI_MAX_EXPECTED_TIME_SECONDS`
- `AI_MAX_PERSONAL_REMARKS_CHARACTERS`
- `AI_MAX_CONCURRENT_PROVIDER_REQUESTS`
- `CLOUDINARY_MAX_IMAGE_BYTES`, `CLOUDINARY_MAX_RAW_BYTES`

Do not set `TEST_DATABASE_URL` in production. `PYTHON_VERSION` is a Render
runtime setting and `PORT` is supplied by Render; neither is an application
secret.

## Vercel frontend

- Import the same GitHub repository and set project root to `frontend`.
- Production branch: `main`.
- Framework preset: Angular.
- Install command: `npm install` (or Vercel's detected equivalent).
- Build command: `npm run build`.
- Output directory: `dist/frontend/browser`.
- Add `REVISEE_API_URL` for Production with the final HTTPS Render base URL.
  It is public build configuration, not a secret.

The build script validates `REVISEE_API_URL` and creates an ignored Angular
production environment file. `vercel.json` provides the SPA fallback required
for direct visits to Angular routes.

After Vercel assigns the stable production domain, place that exact origin in
Render's `CORS_ORIGINS`, then redeploy the backend before testing authentication.

## Release checklist

- [ ] Historical JWT secret assessed and rotated if it was ever used.
- [ ] Git working tree and index reviewed; no secrets tracked or staged.
- [ ] Neon recovery point/procedure recorded and tested by the owner.
- [ ] Database readiness script reports repository head and required schema.
- [ ] All Render `sync: false` variables populated without copying them to Git.
- [ ] Existing BYOK keyring copied exactly to Render through its secret UI.
- [ ] Vercel `REVISEE_API_URL` set to the final Render HTTPS origin.
- [ ] Render `CORS_ORIGINS` set to exact Vercel/custom HTTPS origins.
- [ ] Backend tests, frontend tests, strict TypeScript, and production build pass.
- [ ] First Render deploy performed manually; `/health` returns 200.
- [ ] API login, registration, file upload, PDF access, generation, and revision
      submission smoke-tested without creating disposable production records.
- [ ] Vercel deployment tested with direct navigation to guarded/public routes.
- [ ] Browser console/network checked for CORS, mixed-content, and 404 failures.
- [ ] Render auto-deploy enabled only after the first release is accepted.

## Rollback

1. Disable Render auto-deploy and pause further Vercel production promotions.
2. Roll Vercel back to the last known-good deployment from its deployment UI.
3. Roll Render back to the last known-good deploy. Do not run Alembic downgrade
   blindly: several Revisee migrations intentionally refuse destructive
   downgrades when user data exists.
4. If the release included an approved migration and application rollback is
   not forward-compatible, stop writes and restore Neon from the recorded
   restore point/branch. Confirm the target time before recovery.
5. Restore the previous Render environment-variable versions, including the
   entire BYOK keyring. Restart and verify `/health`, authentication, owned data,
   and PDF access before reopening traffic.
