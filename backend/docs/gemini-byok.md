# Gemini BYOK operations and security

Revisee's Gemini BYOK feature is optional. The normal `GOOGLE_API_KEY` remains
the Revisee-provided generation option. A personal key is used only after the
authenticated user explicitly selects its database ID for a generation request.
There is no fallback to the Revisee-provided key after a personal-key failure.

## Server-side keyring

Personal keys use AES-256-GCM authenticated encryption. Each value has a fresh
96-bit nonce and is bound to its user ID, credential ID and provider through
authenticated associated data. The database stores ciphertext, nonce, key
version, a SHA-256 duplicate-detection fingerprint and four-character display
hint. It never stores plaintext. API responses contain only the name, status and
masked hint.

Generate a 32-byte key with an approved secret-management tool and encode it as
URL-safe base64. Configure the keyring outside source control:

```dotenv
BYOK_ACTIVE_ENCRYPTION_KEY_VERSION=v1
BYOK_ENCRYPTION_KEYS={"v1":"<urlsafe-base64-encoded-32-byte-key>"}
```

Keep this secret in the deployment secret manager, separate from `SECRET_KEY`
and Gemini keys. Losing every configured encryption key makes stored credentials
unrecoverable. Back up the keyring separately under the same recovery controls as
the database.

For server-key rotation, add `v2` while retaining `v1`, then make `v2` active.
New and user-replaced credentials are encrypted with `v2`; old credentials
remain readable with `v1`. Have users replace each stored key (the provider key
may be unchanged) to re-encrypt it. Confirm no `v1` rows remain before removing
`v1` from the keyring. Provider-key rotation uses `PATCH /ai-credentials/{id}`;
the replacement is validated before the old ciphertext is replaced.

Deleting a credential removes its encrypted secret and recorded per-credential
usage. Historical generation events retain their content metadata but their
credential reference becomes null. Existing learning items and questions remain.

## Migration procedure

Migration `20260915_0008` creates `ai_credentials`, `ai_credential_usage`, and an
optional credential reference on `ai_generation_events`. It does not backfill or
touch learning content. Revisee never runs migrations automatically on startup.

Before applying it to a non-test database:

1. Take and verify a PostgreSQL backup/snapshot and separately verify keyring
   recovery material.
2. From `backend`, run `.venv\\Scripts\\alembic.exe current` and
   `.venv\\Scripts\\alembic.exe heads` and confirm the intended database without
   printing its URL.
3. Review pending SQL with `.venv\\Scripts\\alembic.exe upgrade head --sql`.
4. With explicit operator approval, run `.venv\\Scripts\\alembic.exe upgrade head`.
5. Verify `alembic current` reports `20260915_0008` and that both new tables are
   present in the application schema.

Recovery is restore-from-snapshot. The downgrade refuses to run while encrypted
credentials exist, preventing silent credential loss.

## Provider disclosure, usage and limits

Personal generation sends the learning-item title, text source and optional
personal remarks to Gemini. The current flow does not send uploaded images or
PDF files to Gemini. Inputs remain bounded by Revisee's source/prompt/remarks
limits; provider calls use configured timeouts, retry attempts and an in-process
concurrency gate. Structured output, ownership, safety framing and deduplication
remain mandatory.

Gemini reports token usage for individual successful responses. Revisee records
that metadata and labels it **Usage recorded in Revisee**. It is not a remaining
quota balance. Gemini limits are project-level and can change by model and tier;
users must consult Google AI Studio for authoritative usage and limits.
