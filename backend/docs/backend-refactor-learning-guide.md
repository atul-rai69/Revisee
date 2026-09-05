# Revisee backend refactor learning guide

This guide is for Atul. It explains not only where the code moved, but why the
new boundaries exist, how a request travels through them, and how to extend the
backend without rebuilding another `routes.py` monolith.

## 1. Starting point

Before the refactor, `src/routes.py` held all 12 API operations. A route could
decode JWTs, query SQLAlchemy, check ownership, upload Cloudinary files, call
Gemini, commit several times, and manually assemble its response. `src/crud.py`
mixed token helpers, request authentication, Cloudinary uploads, Gemini calls,
and revision persistence. All 13 SQLAlchemy models lived in `src/model.py`, and
all request/provider/response schemas lived in `src/schema.py`.

Large files were a symptom, not the root problem. The important issue was
coupling: changing Gemini could affect authentication imports, a commit in the
authentication dependency could commit feature work, and a route could forget
an ownership filter. Testing a single business rule required importing real
provider clients and database configuration.

Representative risks were:

- `register` and `login` stored and compared plaintext passwords.
- `delete_learning_item` selected only by item ID, not owner.
- `generate_revision` was unauthenticated and duplicated revision persistence.
- `create_learning_item` committed partial state before external work finished.
- label IDs were trusted without proving that they belonged to the user.
- raw Gemini JSON was indexed without validating its structure.
- provider output was printed and raw exception text could reach clients.
- synchronous SDK work ran inside `async def`, blocking the event loop.
- configuration depended on the process working directory and import side effects.

The Angular application also established compatibility constraints. It calls
root URLs such as `/login`, `/labels`, `/learning-items`, and the singular
`/learning-item/{id}`. It expects comma-separated labels/media, `isCorrect`, a
DELETE body containing `id`, and the existing message wrappers. Those shapes are
preserved even where a new API would normally be designed differently.

## 2. Final architecture

```text
backend/
├── alembic/                 # reviewed schema history
├── docs/                    # this architectural record
├── scripts/                 # explicit operational commands
├── tests/                   # unit and PostgreSQL integration tests
└── src/
    ├── api/                 # central router and FastAPI dependencies
    ├── core/                # validated config, security, app errors
    ├── db/                  # Base, session factory, model registry
    ├── integrations/        # Gemini and Cloudinary adapters
    ├── modules/
    │   ├── auth/
    │   ├── labels/
    │   ├── learning_items/
    │   ├── revisions/
    │   ├── dashboard/
    │   └── mastery/
    └── main.py              # app construction and middleware
```

Each active feature owns its router, schemas, service, repository, and models
when those layers solve a real problem. Dashboard has no models because it is a
read view over other features. Mastery currently has only models because the
tables exist but the behavior has not been implemented. No placeholder services
or routers were created.

The dependency direction is:

```text
HTTP → router → service → repository → SQLAlchemy/database
                     └──→ provider protocol → Gemini/Cloudinary adapter
```

This is a modular monolith: one deployable FastAPI process and one database,
with internal feature boundaries. It fits Revisee because the features share
users, learning items, questions, labels, and transactions. Microservices would
add network failures, distributed transactions, multiple deployments, tracing,
and contract coordination before the product needs independent scaling.

## 3. Decision log

| Decision | Problem | Alternatives | Choice and reason | Trade-off/reconsider when |
|---|---|---|---|---|
| Feature-first modules | Global layer folders become new mega-folders | Layer-first or microservices | Keep each feature's HTTP, behavior, and persistence code together | Cross-feature reads require disciplined imports; reconsider only if a domain becomes independently deployable |
| Thin routers | Routes contained business and SQL logic | Keep smart controllers | Routers parse HTTP and delegate | More files, but tests and ownership rules become explicit |
| Service-owned transactions | Repository/route commits produced partial state | Repository commits or a DI unit-of-work framework | Services call commit/rollback; repositories only stage/query data | Services must be reviewed for transaction boundaries |
| Small repository functions | Raw queries obscured ownership and PostgreSQL SQL | Generic `BaseRepository` | Explicit functions such as `find_owned` | Some repetition is intentional; introduce shared abstractions only after repeated real behavior appears |
| Split models with a registry | One 405-line file hid domain ownership | Keep one model file | Feature model files plus `src.db.models` registration | Alembic must import every module; registry tests guard this |
| Named PostgreSQL enums | Unnamed existing enums could not create a blank PostgreSQL schema | VARCHAR/check constraints | Stable `media_type_enum` and `answer_option_enum` names | Existing databases must be compared before stamping |
| Root API paths | Angular depends on legacy URLs and bodies | `/api/v1` now or aliases | Preserve exact roots during this refactor | REST cleanup/versioning remains future work |
| Argon2id with temporary plaintext upgrade | Existing registrations wrote plaintext; Passlib/bcrypt versions were incompatible | bcrypt direct or forced reset | `pwdlib[argon2]`, upgrade plaintext after a valid login | Compatibility branch is temporary and must be removed after migration verification |
| Concealed ownership failures | `403` can reveal that another user's ID exists | Differentiate 403/404 | Return 404 for foreign and missing owned resources | Operators use logs/tests, not public distinction, for diagnosis |
| Sync SQLAlchemy/provider boundary | Current SDKs and ORM are synchronous | Convert the project to async | Use synchronous route functions so FastAPI uses its thread pool | Introduce async only when the whole call chain supports it and measurement justifies it |
| No queue/status columns | Structural cleanup should not add infrastructure/schema state | Celery/Redis now | Isolate generation behind a protocol/service | Requests still wait for Gemini; queue when latency/volume requires it |
| Provider calls outside DB write transactions | Slow external calls held or fragmented database work | One long transaction | Validate/generate/upload first, persist once | External work cannot be rolled back; Cloudinary needs compensation |
| Dedicated PostgreSQL tests | SQLite cannot execute `string_agg`, `array_agg`, or PostgreSQL epoch expressions | SQLite or normal development DB | Require `TEST_DATABASE_URL`, never fall back | Developer must provision a disposable PostgreSQL database |
| Alembic baseline without automatic stamping | Existing DB has no trusted migration history | Assume metadata matches | Baseline blank databases; inspect before stamping existing databases | Adoption is a manual operational step |

## 4. Old-to-new mapping

| Original | Original element | New location/responsibility | Behavior change |
|---|---|---|---|
| `routes.py` | register/login/logout | `modules/auth/router.py` → `AuthService` | Secure hash, atomic user/session, uniform 401 |
| `crud.py` | token helpers | `core/security.py` | Central JWT policy |
| `crud.py` | `get_current_user` | `api/dependencies.py` and auth service/repository | Session is bound to JWT user |
| `routes.py` | label operations | labels router/service/repository | Explicit owner queries |
| `routes.py` | learning-item creation | learning-item service/repositories | One DB commit and upload compensation |
| `routes.py` | item detail/delete | learning-item service/repository | Foreign/missing IDs return 404; delete cleans storage best-effort |
| `routes.py` | dashboard queries | dashboard repository/service | Same public shape; SQL is isolated |
| `crud.py`/`routes.py` | duplicate generation | revision service/repository | One validation/persistence path |
| `crud.py` | Cloudinary upload | storage protocol and adapter | Explicit configuration, mockable cleanup |
| `google_config.py`/`crud.py` | Gemini client/call | AI protocol and Gemini adapter | Lazy client, provider errors sanitized |
| `prompts/revision_prompt.py` | prompt | `modules/revisions/prompt.py` | Malformed `difficulty_level` example fixed |
| `schema.py` | API/provider DTOs | feature `schemas.py` files | AI constraints and safe list defaults |
| `model.py` | ORM tables | feature `models.py` files | Same table/column names; PostgreSQL enums receive names |
| `settings.py` | environment reads | `core/config.py` | Typed, validated, cwd-independent settings |
| `db.py` | Base/session | `db/base.py`, `db/session.py` | Test URL is selected only in test mode |

## 5. Function and module reference

| Element | Caller/dependencies | Result/errors/I/O | Why it belongs there |
|---|---|---|---|
| `get_settings` | app, DB, provider factories | Cached validated settings; configuration error; file/env I/O | Core application policy |
| `hash_password`/`verify_password` | auth service and migration | Argon2 hash or verification result; CPU work | Security policy independent of HTTP/DB |
| `create_access_token`/`decode_access_token` | auth service | JWT or `AuthenticationError`; no external I/O | Central cryptographic boundary |
| `get_auth_context` | protected routers | Authenticated user/session; DB I/O via auth service | FastAPI-specific dependency composition |
| `AuthService.register` | auth router | token response; conflict/DB error; controls transaction | User/session workflow |
| `AuthService.login` | auth router | token response; 401; upgrades legacy password and controls transaction | Authentication business rule |
| `AuthService.authenticate` | auth dependency | `AuthContext`; 401; session/user DB I/O | Authentication plus session validity |
| `LabelService` methods | labels router | labels/mutation wrappers; 404; DB transaction for writes | Label ownership and workflows |
| `LearningItemService.create` | learning router | legacy message; provider/domain/DB errors; provider and DB I/O | Cross-repository/provider workflow and compensation |
| `LearningItemService.get_detail` | learning router | compatibility response; 404; DB reads | Response composition is application behavior, not HTTP parsing |
| `LearningItemService.delete` | learning router | `None`; 404/DB error; DB transaction and storage cleanup | Ownership and mixed-side-effect decision |
| `RevisionService.generate_content` | learning and revision services | validated DTO; 502; Gemini I/O | Canonical provider validation seam |
| `RevisionService.generate_for_owned_item` | `/generate` router | legacy message; 404/502/DB error; DB/provider I/O | Authorization and generation workflow |
| Feature repositories | their services | ORM rows/counts; DB I/O; no commits | Query/persistence composition |
| `GeminiAIProvider.generate` | revision service | raw text; provider unavailable; network I/O | Provider-specific SDK behavior |
| `CloudinaryStorageProvider` | learning service | asset/delete; provider error; network I/O | Provider-specific storage behavior |
| `migrate_plaintext_passwords` | operator only | count-only report; explicit DB I/O and commits | Operational action must not run at startup |

Repositories never control transactions. Routers never perform database or
provider work. Services own commits because only the service knows whether the
whole business operation succeeded.

## 6. Request-flow walkthroughs

### Registration

```text
POST /register query parameters
→ auth router
→ AuthService.register
→ auth repository checks username/email
→ core security hashes password
→ user and session are flushed/committed together
→ JWT returned with legacy response fields
```

If either insert fails, both are rolled back. The query-parameter contract is
kept only for compatibility and should be replaced with JSON in a versioned API.

### Login

```text
POST /login JSON
→ auth router
→ AuthService.login
→ repository loads user
→ Argon2 verification OR temporary constant-time plaintext check
→ plaintext value is immediately upgraded when valid
→ new session committed
→ JWT response
```

Wrong password and unknown user both produce the same 401 response.

### Authenticated request

```text
Authorization: Bearer token
→ HTTPBearer dependency
→ JWT decode
→ session lookup constrained by session_id + user_id + active
→ expiry and user lookup
→ last_used_at commit
→ AuthContext/current user
→ feature router
```

A JWT proves possession of a signed token; it does not by itself prove ownership
of a requested learning item. Feature repositories still filter by user ID.

### Creating a learning item, labels, media, and revision

```text
multipart request
→ router parses JSON label IDs
→ auth dependency
→ LearningItemService
→ label repository verifies every owner ID
→ read transaction ends
→ RevisionService → Gemini adapter → Pydantic validation
→ Cloudinary adapter uploads media, tracking public IDs
→ one DB transaction inserts item/labels/media/revision content
→ success message
```

Gemini and uploads occur outside the DB write transaction. If an upload or DB
write fails, uploaded assets from this request are deleted in reverse order.
Compensation is best effort because PostgreSQL cannot roll back Cloudinary.

### Retrieving learning-item and dashboard data

```text
GET request
→ auth dependency
→ thin feature router
→ service
→ ownership-aware or user-scoped repository queries
→ service maps compatibility response
→ Pydantic response validation
```

The dashboard repository deliberately contains PostgreSQL-specific aggregation.
The learning-item detail response keeps comma-separated labels/media because the
current Angular code splits those strings.

### Generating revisions

```text
POST /generate
→ auth dependency
→ RevisionService verifies owned item before provider cost
→ Gemini adapter
→ JSON + Pydantic validation
→ generated records staged by revision repository
→ service commit
→ legacy message response
```

Invalid JSON or invalid fields cause a sanitized 502 and no persistence. Repeated
generation currently appends key points/questions because replacement semantics
were intentionally deferred.

### Deleting a learning item

```text
DELETE /learning-items with {id}
→ auth dependency
→ service loads owned item and media IDs
→ related key points/item are deleted and DB commit succeeds
→ Cloudinary assets are deleted best-effort
→ legacy 200/null response
```

The database is authoritative. If cleanup fails after commit, the deletion is
not falsely reported as failed; a warning records only the failure count.

## 7. Concepts used

Each row answers: what it means, where Revisee uses it, why it helps, when it is
too much, and the mistake to avoid.

| Concept | Meaning and Revisee use | Why useful | Overengineering point | Mistake to avoid |
|---|---|---|---|---|
| Separation of concerns | HTTP, workflows, SQL, and providers have separate modules | A provider or query can change independently | Splitting every one-line function | Moving code without changing dependency direction |
| Single Responsibility | A router translates HTTP; a repository composes SQL | Smaller reasons to change | Treating “one class” as automatically SRP | A service becoming a new `crud.py` |
| Dependency direction | Outer HTTP code depends inward on application behavior | Prevents FastAPI from infecting domain/persistence code | Complex clean-architecture rings for a small app | Repositories importing routers |
| Dependency inversion | Services use `AIProvider`/`StorageProvider` protocols | Tests replace paid services and Gemini can be swapped | Interface for a value with no alternate behavior | Importing concrete Gemini in the service |
| Repository pattern | Named functions contain SQLAlchemy queries | Ownership filters and PostgreSQL SQL become reviewable | Generic base repository/ORM wrapper | Hiding commits inside repositories |
| Service layer | Coordinates a complete use case | Correct transaction and compensation decisions | Service for a read that is already trivial and stable | Putting request parsing or HTTP exceptions in services |
| Dependency injection | FastAPI supplies DB/auth/provider dependencies | Request scoping and test overrides | Adding a second DI framework | Constructing real providers inside route bodies |
| Modular monolith | One deployable app with feature boundaries | Low operational cost with scalable code ownership | Premature network services | Assuming folders enforce boundaries without import rules |
| Feature-first architecture | Auth/labels/items/revisions own their layers | New features do not congest global folders | A feature package for a single unrelated helper | Global `services/` and `repositories/` mega-folders |
| API versioning | New incompatible contracts get a versioned surface | Allows later cleanup without silent Angular breakage | Versioning unchanged internal refactors | Adding `/api/v1` and breaking existing clients |
| DTO/schema | Pydantic types validate API/provider data | ORM stays private; Gemini output is checked | A DTO for every internal scalar | Returning SQLAlchemy models as the long-term public contract |
| Authentication | Establishes who sent the request | JWT/session dependency provides current user | Custom auth framework before requirements demand it | Treating a valid JWT as resource authorization |
| Authorization/ownership | Checks what that user may access | `find_owned(id, user_id)` isolates learning items | Role engine for simple owner-only access | Querying only by resource ID |
| Unit of work/transaction | One business operation commits atomically | Registration and item persistence commit as units | A framework around one SQLAlchemy session | Multiple unexplained commits across layers |
| Rollback | Discards uncommitted DB work | Service catches persistence failure and rolls back | Catching every exception at every layer | Returning success before commit finishes |
| Compensation | Reverses external side effects best-effort | Failed creation deletes uploaded Cloudinary assets | Distributed saga infrastructure at current scale | Assuming DB rollback deletes cloud files |
| Idempotency | Repeating an operation has a controlled result | Password migration skips approved hashes | Idempotency keys for every local read | A migration that hashes a hash again |
| Configuration management | Typed settings validate environment input | Test DB and secrets are selected explicitly | Remote config service for local app | Repeated `load_dotenv` and cwd-dependent behavior |
| Migrations | Versioned database DDL | Alembic baseline creates clean test/new DBs | Auto-running migrations at import | Stamping an unverified existing schema |
| Background jobs | Work continues outside request lifecycle | Future Gemini generation queue | Celery/Redis before measured need | Holding HTTP/DB transactions open for long AI calls |
| Sync versus async | Async helps only when the full I/O chain is async | Sync providers/routes run in FastAPI thread pool | Converting SQLAlchemy only for style | Calling blocking SDKs directly in `async def` |
| Test doubles/overrides | Fakes replace external boundaries | Tests make no paid Gemini/Cloudinary calls | Mocking every internal function | Mocking SQLAlchemy in integration tests instead of using PostgreSQL |

## 8. Adding future features

### Spaced repetition

Create a `spaced_repetition` module when scheduling behavior exists. Its router
accepts review actions; service calculates next-review state; repository reads
questions/mastery and persists schedules; schemas define review DTOs. Add an
Alembic migration for scheduling fields/tables and test interval rules, ownership,
and transaction rollback. It needs no integration unless notifications are sent.

### Mastery tracking

Expand the existing `mastery` module. Add schemas/service/repository only when
attempt recording is implemented. The service updates label and item mastery in
the same transaction as an attempt. Test repeated attempts, score bounds,
cross-user isolation, and concurrent-update behavior. Existing mastery tables may
need constraints or numeric precision migrations after real scoring rules exist.

### Weak-area analysis

Prefer a read-oriented analytics service over adding logic to dashboard routes.
It can query mastery/attempt tables through a repository and expose response-only
schemas. Create a separate module if weak-area endpoints/rules grow independently;
otherwise begin inside mastery. Test ranking, ties, empty users, and user scoping.

### Notifications

Create a `notifications` module for preferences, notification records, and
delivery orchestration. Provider-specific email/push code belongs under
`integrations`. Database migrations store preferences and delivery state. Unit
tests fake the provider; integration tests verify preferences and ownership.
Queue/retry infrastructure is justified once delivery is asynchronous.

### Sharing

Create a `sharing` module because access rules differ from ownership. Its service
must define owner, recipient, public-link, expiry, and revocation rules. Repository
queries must never bypass those rules. Add share tables via Alembic and tests for
revoked/expired links, foreign users, guessing tokens, and item deletion.

### Analytics

Keep product analytics separate from learning dashboard summaries. Define the
events and privacy policy first. A service records allowed events; repositories
aggregate only necessary data; third-party analytics SDKs live in integrations.
Test consent, data minimization, failure isolation, and never include secrets or
study content in event payloads.

## 9. Security lessons

Plaintext passwords let anyone with a database copy immediately impersonate every
user. Password hashing is deliberately slow and salted. Revisee uses Argon2id, so
two users with the same password receive different hashes and verification does
not reveal the original password.

The temporary legacy branch compares plaintext with a constant-time function and
immediately upgrades a successful login. It is not a permanent supported format.
Run the reviewed migration, confirm zero plaintext candidates, then remove and test
the branch.

Authentication answers “who are you?” Ownership answers “may you access this
specific item?” Every item repository lookup includes both item and user ID.
Checking only `LearningItem.id` allowed one authenticated user to delete another
user's data.

JWTs carry signed claims; they do not encrypt those claims, revoke themselves, or
replace database authorization. Revisee binds `sub` to the stored session user,
checks activity/expiry, and still performs owner-scoped resource queries.

Secrets live only in ignored `.env` or deployment environment variables. The
tracked example contains placeholders. Never log tokens, passwords, database
URLs, API keys, full Gemini study output, or Cloudinary secrets.

## 10. Testing lessons

Characterization tests protect existing URLs and wire shapes during movement.
They are not permission to preserve vulnerabilities. Security tests instead state
the corrected behavior: hashes, 401s, 404 ownership concealment, validated AI, and
rollback.

Unit tests exercise security and revision validation without a database or
network. Integration tests use real SQLAlchemy and PostgreSQL because the queries
depend on PostgreSQL semantics. They override only Gemini, Cloudinary, and the
request-scoped DB session.

`TEST_DATABASE_URL` is mandatory. Tests refuse a URL without `test` in the
database name and never substitute `DATABASE_URL`. Per-test outer transactions
and savepoints make application commits reversible. Alembic prepares the dedicated
schema. Tests must never point at development or production data.

Mock provider boundaries because they cost money, depend on networks, and return
nondeterministic results. Do not mock Pydantic validation, password hashing, JWT
logic, repository SQL, or PostgreSQL in the integration suite.

## 11. Mistakes and lessons

- Importing the old app from the repository root failed because `load_dotenv()`
  depended on the working directory. Explicit backend-relative settings fixed it.
- The machine had a generic `DEBUG=release` environment variable. A settings field
  named `DEBUG` collided with it and prevented startup. Revisee now accepts the
  scoped `REVISEE_DEBUG`/`APP_DEBUG` names.
- The installed Passlib and bcrypt versions failed a real hashing smoke test.
  Argon2id through `pwdlib` replaced that incompatible combination.
- The original unnamed SQLAlchemy enums could not compile PostgreSQL `CREATE TYPE`
  statements. Stable enum names were added and the discovery is documented for
  existing-schema comparison.
- `/generate` was assumed to be frontend-compatible during early analysis. Source
  inspection showed the Angular request lacks `learning_item_id` and expects a
  different response. No unsafe title-based lookup was added.
- A test PostgreSQL URL was not available during implementation. Unit/static and
  offline-Alembic checks ran; online integration/Alembic verification remains an
  explicit environment-dependent step.

Future failures belong in this section with the observed symptom, root cause,
diagnostic method, correction, and lesson. Hiding a failed approach removes useful
engineering knowledge.

## 12. Interview-ready explanations

**Why restructure the backend?**  The problem was mixed responsibilities, not
line count. Routes controlled HTTP, authorization, SQL, transactions, and external
providers, making ownership mistakes and isolated tests likely.

**Why a modular monolith?**  Revisee's features share users, items, labels, and
transactions. A modular monolith provides clear code ownership without distributed
systems overhead. Provider and feature boundaries can later become service seams
if measured scaling needs justify it.

**Why a service layer?**  A use case such as item creation spans ownership checks,
AI validation, uploads, compensation, and one DB commit. That workflow belongs in
one application-level place rather than a route or repository.

**Why not SQLAlchemy in routes?**  Owner filters and database-specific aggregation
are persistence concerns. Repositories make them reusable, testable, and easy to
review for missing user constraints.

**How is ownership enforced?**  Authentication supplies the current user, then
repository functions such as `find_owned` query by resource ID and user ID. Missing
and foreign resources both return 404.

**How are transactions handled?**  Repositories stage work; services commit or
roll back the entire database portion of a use case. Slow provider calls occur
outside the DB write transaction.

**What if PostgreSQL succeeds but Cloudinary fails during deletion?**  The database
is authoritative and deletion remains successful. Cleanup is best effort and an
orphan warning is recorded. A retry/outbox is the later robust solution.

**What if Cloudinary succeeds but item persistence fails?**  The service tracks
uploads and compensates by deleting them. Compensation can also fail, so it logs a
sanitized count while preserving the original error.

**How is Gemini isolated?**  The service depends on an `AIProvider` protocol. Only
the adapter imports Google's SDK. Tests supply deterministic fakes, and another
provider can implement the same interface.

**How would AI generation scale?**  Add persisted generation states and enqueue the
service operation. A worker performs Gemini work and transitions to READY/FAILED;
the HTTP request returns 202 and the UI polls or receives events.

**How do tests make the architecture safer?**  Contract tests protect Angular
compatibility, security tests protect isolation, unit tests cover validation and
compensation, and PostgreSQL tests protect real query behavior.

## 13. Revision checklist

### Key concepts

- Router parses HTTP; service owns rules/transactions; repository owns SQL.
- Authentication never replaces resource ownership.
- Database rollback cannot undo external provider work.
- Async syntax does not make synchronous I/O non-blocking.
- Migrations are reviewed history, not automatic schema guessing.

### Important files to revisit

- `src/api/router.py` for the public endpoint assembly.
- `src/api/dependencies.py` for request-scoped auth/provider dependencies.
- `src/core/security.py` for password/JWT policy.
- Learning-item and revision services for the main workflows.
- `alembic/env.py` and the baseline before any schema change.
- This decision log before adding new architecture.

### Common mistakes to avoid

- Adding a query or commit to a router.
- Adding a generic `utils.py` instead of naming a responsibility.
- Querying an owned resource by ID alone.
- Returning ORM models as an uncontrolled public contract.
- Calling real Gemini/Cloudinary in tests.
- Pointing tests or migrations at an unconfirmed database.
- Logging provider payloads or secrets.

### Self-testing questions

1. Why does `find_owned` take both item ID and user ID?
2. Which layer decides when item creation commits?
3. Why is Cloudinary cleanup compensation rather than rollback?
4. Why does a valid JWT not authorize access to every item?
5. What evidence would justify adding a queue or microservice?

### Small exercises

- Add a label-delete use case with ownership and tests without touching another
  module's router.
- Add a fake AI response with an invalid correct-answer index and trace the error.
- Draw the transaction/external-side-effect timeline for item creation.
- Write a true consecutive-streak algorithm as a unit-tested service function.
- Draft—but do not apply—an Alembic migration for a revision status column.

### Future-feature review checklist

- Is this behavior part of an existing feature or a genuinely new module?
- Are HTTP, business, SQL, and provider responsibilities separated?
- Does every owned query include user scope?
- Is the public request/response schema explicit and compatible?
- Who owns commit and rollback?
- Are slow external calls outside DB write transactions?
- Is compensation/retry behavior defined?
- Does a schema change have a reviewed Alembic migration?
- Do tests use `TEST_DATABASE_URL` and provider fakes?
- Are secrets and user content excluded from logs?

## 14. Revision-session Phase 1: stored-question quizzes

Phase 1 adds the foundation for taking a quiz without implementing submission,
mastery, weak-area analysis, or AI shortage generation. A user can create a
RANDOM or LABEL session from questions that already exist, then retrieve that
session later with exactly the same questions in exactly the same order.

### Why selected questions are persisted

Selecting questions only when the HTTP response is built would make a quiz
unstable. Refreshing the page could return a different sample, and there would be
no authoritative list against which a future submission could be validated.
`revision_session_questions` therefore records every selection and its unique
`question_order` before the API returns `201`.

The public `session_question_id` identifies this occurrence of a question inside
a session. The live question-bank ID is deliberately not part of the pre-submit
DTO. A later submission feature can validate answers against session membership
rather than trusting arbitrary question IDs supplied by the browser.

### Live bank records versus immutable history

`questions` and `learning_item` are editable product data. A revision session is
historical evidence: it must continue to mean what the user actually saw. Each
session-question row therefore snapshots:

- learning-item title;
- question text and all four options;
- internal correct option and explanation;
- difficulty and expected time; and
- source classification.

Application repositories create these fields once and provide no operation that
updates them from later bank edits. Source question, item, and label references
are nullable and use `ON DELETE SET NULL`. Removing live content can remove the
link but does not cascade-delete the snapshot. Account deletion may still remove
the user's sessions through the user/session ownership cascade; that is a
separate data-retention policy.

The correct option and explanation must exist internally so a future server-side
submission can grade the exact historical question. They are intentionally absent
from `RevisionSessionQuestionResponse`. Separate pre-submit and future result DTOs
prevent accidental answer leakage.

### RANDOM selection

The repository retrieves only structurally usable questions joined through
learning items owned by the authenticated user. `select_random_question_ids`
deduplicates IDs and samples without replacement. It accepts a randomizer so
production receives normal randomness while tests can supply a seeded
`random.Random` and reproduce the result. A shortage returns `409` before any
session row is added.

### LABEL quotas and maximum matching

A LABEL request supplies `questions_per_label`; its total is derived as:

```text
number of selected labels x questions_per_label
```

Every label must fill its exact quota with unique questions. A question from an
item carrying two selected labels is eligible for both quotas, but may occupy only
one session position. A naive greedy algorithm can consume a shared question for
a rich label and leave a scarce label short even when a complete assignment
exists.

`selection.py` models quota slots and candidate questions as a bipartite graph and
uses augmenting-path maximum matching. Scarcer labels are considered first, while
augmenting paths can reassign earlier matches when that enables another slot.
Final display order is round-robin in the original label request order. Shortage
counts represent the maximum assignable unique set rather than misleading raw
candidate-pool sizes.

### Create request flow

```text
POST /revision-sessions
-> authentication dependency
-> discriminated RANDOM/LABEL request schema
-> RevisionSessionService.create
-> ownership-aware repository candidate queries
-> pure RANDOM or LABEL selector
-> service creates session + label snapshots + question snapshots
-> repository flushes IDs (never commits)
-> service commits once
-> safe RevisionSessionResponse
```

The request models use `extra="forbid"`. RANDOM accepts `question_count` and
rejects label fields. LABEL accepts `label_ids` and `questions_per_label` and
rejects `question_count`. `allow_ai_generation` is stored for forward
compatibility but never calls Gemini in Phase 1.

If selection, snapshot construction, flushing, or committing fails, the service
rolls back the complete operation. On shortage, matching finishes before any
session persistence and the structured `409` reports total and per-label gaps.

### Resume request flow

```text
GET /revision-sessions/{session_id}
-> authentication dependency
-> repository query constrained by session ID + user ID
-> label snapshots ordered by original request order
-> question snapshots ordered by persisted question_order
-> same safe RevisionSessionResponse
```

Resume never queries live question content and never resamples. Missing and
foreign-owned sessions share the concealed `404` policy.

### Phase 1 module and function mapping

| Module or function | Responsibility |
|---|---|
| `revisions.schemas.RandomRevisionSessionRequest` | RANDOM-only fields and bounds |
| `revisions.schemas.LabelRevisionSessionRequest` | Unique labels, per-label quota, derived total |
| `revisions.schemas.RevisionSessionResponse` | Stable answer-safe create/resume contract |
| `revisions.selection.select_random_question_ids` | Seedable selection without replacement |
| `revisions.selection.select_label_questions` | Quota-aware unique maximum matching and round-robin order |
| `revisions.repository` session functions | Owned candidate SQL, snapshot staging, ordered reads; no commits |
| `RevisionSessionService.create` | Selection orchestration and one transaction boundary |
| `RevisionSessionService.resume` | Owned historical-session retrieval |
| `RevisionSession`, `RevisionSessionLabel`, `RevisionSessionQuestion` | Session metadata, selected-label snapshots, immutable ordered question snapshots |

### Unit and integration testing

Pure selection, schema, and service-rollback tests do not need configuration or a
database. `tests/conftest.py` only reads `TEST_DATABASE_URL` when integration
execution is explicitly requested. Normal pytest discovery marks PostgreSQL tests
as skipped with a clear reason. `--run-integration` makes a missing, non-PostgreSQL,
normal-database-equivalent, or non-test-named URL a hard error.

PostgreSQL integration tests cover real ownership joins, constraints, atomic
persistence, resume ordering, and `ON DELETE SET NULL`. SQLite is not a substitute
for these semantics. At this checkpoint the unit suite and offline checks pass,
but PostgreSQL verification remains pending because a dedicated
`TEST_DATABASE_URL` has not been supplied.

### What this foundation enables without implementing it

- Phase 2 can calculate a precise total or per-label shortage before asking an AI
  provider for only the missing questions.
- Phase 3 can validate submitted `session_question_id` values against the immutable
  session and grade from the hidden snapshot answer.
- Attempts and mastery can reference what the user actually saw rather than a
  mutable or deleted bank record.

Those behaviors are deliberately absent from Phase 1. The deprecated
`revision_sessions.quiz_type` column also remains until a separately approved
cleanup migration is safe against real PostgreSQL data. The Phase 1 downgrade
refuses to discard LABEL history, deleted source references, or snapshots that
have diverged from live content because the older schema cannot represent that
history faithfully.

## 15. AI-generation Phase 2A: safe question-only foundation

Phase 2A introduces the internal foundation for creating additional bank
questions without activating session-shortage generation or adding a public AI
endpoint. Existing learning-item creation and `/generate` continue to use the
legacy full-revision operation and keep their existing successful contracts.

### Why question-only generation is separate

Full revision generation creates theory, key points, and five questions as one
product workflow. A future quiz shortage has a narrower requirement: request an
exact number of questions grounded in one owned item. Reusing the full prompt
would regenerate unrelated theory, waste provider tokens, and make partial
question validation difficult.

`revisions/generation` therefore provides a question-only operation. It can be
called later by a session-shortage or proactive workflow without either workflow
knowing anything about Gemini. Phase 2A deliberately leaves it disconnected from
public routers so enabling the foundation cannot unexpectedly spend provider
credits.

### Provider abstraction and token metadata

`AIProvider.generate` remains for compatibility. The new
`generate_structured` method accepts a provider-neutral `StructuredAIRequest`
and returns `StructuredAIResult`. Only the Gemini adapter knows the Gemini SDK.
The application receives text, provider/model identifiers, a response ID, and
optional token counts through its own types.

Provider-reported input, output, total, cached, thought, and tool-token counts are
stored as actual values when available. Missing provider metadata remains null.
The application may store `ceil(prompt characters / 4)` in the separately named
estimated-input field, with an explicit boolean flag. An estimate is never copied
into an actual token column.

### Source safety and prompt-injection boundary

One call uses one authenticated user's learning item. Source preparation prefers
the title, generated theory, and ordered key points. Raw editor notes are used
only as a fallback. The standard-library HTML parser removes script and style
content, decodes entities, preserves useful block boundaries, and collapses
whitespace before deterministic truncation.

A title without theory, key points, or cleaned notes is rejected as insufficient
source material. This prevents a broad title from silently turning the operation
into unrelated general-knowledge generation.

Media bytes, file contents, URLs, other learning items, secrets, and internal
metadata are never included. The prompt places prepared text inside explicit
`UNTRUSTED_LEARNING_ITEM_SOURCE` delimiters and instructs the provider to treat
embedded commands as data. Angle brackets in source text are escaped so the
source cannot close or reopen the structural delimiter. This reduces
prompt-injection risk, but it is not a perfect security boundary; output
validation and ownership checks remain mandatory.

The per-call source identifier is a SHA-256 digest of prepared source text. It is
used only for internal correlation and change detection. It is not authentication,
encryption, or proof that private content cannot be guessed. No additional secret
is required at application startup for this internal identifier.

### Per-entry validation and partial results

The parser rejects oversized, malformed, or incorrectly shaped top-level JSON.
Inside a valid `questions` list, each entry is validated independently. One bad
question increments the rejected count without discarding valid siblings.
Question models forbid extra fields, require four distinct nonblank options,
normalize an index or A-D answer to `"0"`-`"3"`, constrain difficulty to 1-3,
bound expected time, and require nonblank question/explanation text. Entries past
the requested count are ignored and counted as excess.

Only validated questions proceed to fingerprinting. This makes malformed output
observable without allowing it into the bank and avoids storing the complete raw
provider response.

### Fingerprinting and its limits

A question fingerprint normalizes question and option text with Unicode NFKC,
case folding, and whitespace collapse. It preserves punctuation, sorts the four
normalized options, serializes deterministic compact JSON, and computes SHA-256.
The database has a partial unique index on learning-item ID plus non-null
fingerprint. Existing questions stay unchanged with null fingerprints; the
service calculates comparable fingerprints in Python while checking legacy rows.

This detects formatting, casing, Unicode, whitespace, and option-order variants.
It does not prove semantic uniqueness: substantially reworded questions can still
express the same concept. Conversely, punctuation is retained to reduce overly
aggressive false matches. PostgreSQL `ON CONFLICT DO NOTHING` handles concurrent
duplicates without aborting the complete generated batch.

### Transaction boundaries and operational records

The canonical internal flow is:

```text
internal application operation
-> ownership-aware source query
-> prepare source and prompt
-> end the read transaction
-> create generation event + call in a short transaction
-> mark processing in a short transaction
-> provider call with no database transaction open
-> validate and fingerprint response
-> recheck source ownership
-> conflict-safe question insert + event/call finalization
-> one final commit
```

Events and calls record only operational facts: ownership, operation, status,
safe counts, template version, provider/model identifiers, optional usage,
response ID, source digest, and safe error code. They never store prompts, raw
notes, complete responses, provider exceptions, keys, tokens, passwords, or
provider URLs. Repositories never commit; the service owns each transaction.

If the provider fails, the event records a sanitized failure code. If final
persistence fails, the question insert and successful finalization roll back
together before the event is marked failed in a separate short transaction.

### Phase 2A module and function mapping

| Module or symbol | Responsibility |
|---|---|
| `integrations.ai.base` | Provider-neutral request, result, usage, and operation types |
| `GeminiAIProvider.generate_structured` | Gemini call and provider-metadata translation |
| `generation.source.prepare_question_source` | Safe one-item source selection and cleaning |
| `generation.prompt.build_question_prompt` | Versioned, count-aware question-only prompt |
| `generation.schemas.parse_question_response` | Bounded JSON parsing and independent entry validation |
| `generation.fingerprint.question_fingerprint` | Deterministic per-item deduplication identity |
| `QuestionGenerationService.generate_for_owned_item` | Ownership, provider, validation, persistence, and transaction orchestration |
| `ai_generation.repository` | Source/event/call persistence operations without commits |
| `revisions.repository.insert_generated_questions_conflict_safe` | PostgreSQL conflict-safe bank insertion |
| `AIGenerationEvent`, `AIGenerationCall` | Safe operation-level and provider-call-level history |

### Testing and verification boundary

HTML cleanup, budgeting, prompting, parsing, fingerprinting, provider mapping,
and legacy-contract tests run without PostgreSQL or Gemini. Integration tests are
authored for the partial unique index, `ON CONFLICT`, foreign keys, migration
shape, and rollback, but remain behind the existing safe `TEST_DATABASE_URL`
guard. Offline Alembic SQL can verify the intended PostgreSQL statements without
opening a database connection.

Phase 2A prepares later session-shortage generation by returning accepted,
deduplicated question IDs and safe counts. It does not yet call this operation
from revision-session creation, impose quotas, expose usage, generate proactively,
or accept feedback. Those changes require their own reviewed phases.

## 16. Quiz submission and mastery: completing the V1 revision lifecycle

Phase 3 turns an immutable `IN_PROGRESS` quiz into an atomic, durable result. It
adds complete-session submission, snapshot-based grading, attempts, live-question
statistics, item and label mastery, and completed-result retrieval. Partial
answers, autosave, weak-area ranking, and SMART selection remain separate work.

### Snapshot-based grading and answer secrecy

The question bank describes what can be selected for a future quiz. A session
snapshot describes exactly what one user saw in one historical quiz. They must
not be treated as the same record: a bank question can be edited or deleted
after the session begins.

Submission therefore grades only `RevisionSessionQuestion` fields. It does not
read the current `Question.correct_option`, explanation, difficulty, or expected
time. Attempts retain a strong reference to the session question and only a
nullable reference to the live question. A deleted source sets that reference to
null while the attempt and result remain meaningful.

The create/resume DTO stays unchanged and never contains answers or explanations.
Only `RevisionSessionResultResponse`, returned after successful completion, owns
answer-bearing fields. Keeping these schemas separate prevents a later refactor
from accidentally exposing an internal snapshot answer through OpenAPI.

### Submission request flow

```text
POST /revision-sessions/{session_id}/submit
-> authentication dependency
-> strict complete-answer request validation
-> owned session SELECT FOR UPDATE
-> immutable session questions in persisted order
-> exact session-question ID set comparison
-> snapshot grading and Decimal delta calculation
-> lock surviving items, questions, and current labels in ID order
-> materialize and lock mastery rows
-> insert attempts
-> atomically upsert live-question statistics
-> update item and label mastery
-> mark session COMPLETED
-> one service-owned commit
-> completed result DTO
```

The submitted IDs must exactly equal the persisted session-question IDs. Missing,
unexpected, and foreign IDs share `ANSWER_SET_MISMATCH`; the error does not reveal
which resource exists. Duplicate IDs are rejected by the Pydantic request model.
The server calculates correctness, so a client cannot submit its own `is_correct`
value.

The owned session row is locked first. Two simultaneous submissions serialize:
the winner commits, and the second sees `COMPLETED` and receives the stable `409`
`REVISION_SESSION_ALREADY_COMPLETED`. A unique attempt per session question and a
composite membership foreign key reinforce this rule in PostgreSQL.

### Result request flow

```text
GET /revision-sessions/{session_id}/result
-> authentication dependency
-> query by session ID + user ID
-> require COMPLETED
-> ordered immutable snapshots + immutable attempts
-> verify complete one-to-one history
-> stable answer-bearing result DTO
```

Results are derived from snapshots and attempts rather than mutable live questions
or current mastery. This means deleting an original learning item cannot change
the question, options, correct answer, explanation, score, or order shown in an
old result. Current mastery is intentionally absent because later practice would
make an old result response change over time.

### Attempts and question statistics

An attempt is immutable evidence of one answer to one persisted session question.
It stores the chosen option, server-calculated correctness, bounded reported time,
the exact mastery delta, and a single UTC submission timestamp. V1 exposes no
attempt edit or delete operation.

`QuestionStatistics` is different: it is a replaceable aggregate for a surviving
live bank question. Its PostgreSQL upsert atomically increments total/correct
counts and exact total seconds. Average time is recalculated from total seconds
and count, avoiding cumulative rounding drift. Deleting the live question removes
this aggregate, but does not remove attempts or historical results.

### Decimal mastery and entity attribution

`calculate_mastery_delta` is pure and uses `Decimal`. Correct hard answers reward
more than correct easy answers; wrong easy answers penalize more than wrong hard
answers. Time changes the strength of the result through bounded multipliers.
Every question delta is rounded to `0.01` with `ROUND_HALF_UP`.

For one submitted session, individually rounded deltas are grouped by entity and
summed. The entity score is then updated and clamped once to `0.00`-`100.00`.
This makes the outcome independent of iteration order. Counters are updated with
the batch totals.

Each answer affects its surviving owned learning item once. Every current,
surviving, user-owned label attached to that item receives the same contribution.
The label used to satisfy a LABEL-session quota is selection metadata, not a claim
that learning happened only in that category. Deleted/detached labels are not
updated; newly attached current labels are.

Review scheduling uses the final entity score and all answers affecting that
entity in the session. Any incorrect answer schedules one day. Otherwise the
intervals are one day below 40, three days from 40, seven days from 60, and
fourteen days from 80. `last_attempt_at`, `last_reviewed_at`, `next_review_at`,
attempt timestamps, and `ended_at` all derive from the same server-side UTC time.

Client-reported time is restricted to 0-3600 seconds but is still untrusted. It
can influence only the authenticated user's own mastery. Trusted active-timer
telemetry would be a later product/security improvement.

### Transaction ownership and locking order

`RevisionSubmissionService` owns one transaction and one commit. Repositories
query, add, execute, lock, and flush, but never commit. An exception at any point
rolls back attempts, statistics, both mastery types, session status, and end time.
No provider or storage call occurs inside this transaction.

All submissions acquire locks in the same order: owned session, learning items,
live questions, current labels, item mastery, then label mastery; IDs are ascending
within each group. Consistent ordering reduces deadlocks when separate sessions
touch the same learning material. Database constraints remain the final defense
against duplicate attempts and cross-session membership mistakes.

### Phase 3 module and function mapping

| Module or symbol | Responsibility |
|---|---|
| `revisions.submission_schemas` | Strict complete-answer request and isolated completed-result DTO |
| `RevisionSubmissionService.submit` | Locking, grading, orchestration, one commit, and rollback |
| `RevisionSubmissionService.result` | Owned reconstruction of stable completed results |
| `revisions.submission_repository` | Owned locks, attempt persistence, statistics UPSERTs, ordered reads |
| `mastery.calculation.calculate_mastery_delta` | Pure Decimal difficulty/time policy |
| `mastery.calculation.aggregate_contributions` | Order-independent per-entity batch totals |
| `mastery.service.apply_mastery_batches` | Clamp, counters, timestamps, and review scheduling |
| `mastery.repository` | Conflict-safe materialization and deterministic mastery-row locks |
| `UserAttempt` | Immutable submitted-answer evidence tied to a session snapshot |
| `QuestionStatistics` | Disposable aggregate for a surviving live bank question |

### Migration reconciliation and verification boundary

Migration `0004` refuses to invent missing history. Legacy attempts lack elapsed
time, mastery delta, and a strong session-question identity; completed legacy
sessions may not have a truthful complete answer set. If either exists, upgrade
stops before structural changes and requires a separately reviewed reconciliation.
Existing mastery values are also validated rather than silently clamped.

Downgrade refuses once a Phase 3 completed session, attempt, or statistics row
exists, or Decimal mastery cannot be restored losslessly to the older integer
schema. This is safer than silently destroying quiz history even if someone has
manually removed only part of the submission evidence.

Pure grading, schema, formula, aggregation, rollback, and secrecy tests run without
a database. PostgreSQL tests cover row locks, concurrent submission, composite
foreign keys, UPSERT arithmetic, deletion behavior, and the migration guards.
They remain unavailable until a dedicated safe `TEST_DATABASE_URL` is supplied;
SQLite cannot validate these PostgreSQL semantics.

Phase 3 creates the evidence needed for future weak-area detection and SMART
quizzes: immutable attempts, accurate counts, Decimal mastery, and review dates.
It deliberately does not choose evidence thresholds, weakness weights, or SMART
selection policies before real behavior and PostgreSQL execution have been
reviewed.

## 17. Weak areas and SMART revision sessions

Phase 4 turns the evidence created by Phase 3 into an explainable read model and
a personalized stored-question strategy. It does not change how mastery is
calculated. That separation is important: reporting and selection may evolve
without rewriting historical learning evidence.

### Initial mastery is not demonstrated weakness

New mastery rows start at `50.00`, and owned items or labels may not have a
mastery row at all. Neither state proves that a learner is weak. Revisee requires
at least three attempts before a score can be called demonstrated weakness.
Three is a simple product heuristic, not statistical confidence: three attempts
could all concern one question. The API therefore reports insufficient evidence
explicitly rather than mixing it into the weak list.

Classification is mutually exclusive and evaluated at one captured UTC `as_of`
time. Missing mastery or fewer than three attempts is
`INSUFFICIENT_EVIDENCE`. With enough attempts, a score below `60.00` is
`DEMONSTRATED_WEAKNESS`. A score of at least `60.00` whose review time has
arrived is `DUE_REVIEW`. Everything else is stable and excluded from the chosen
classification page. A weak and overdue entity remains weak, while `is_due`
still explains its urgency; an overdue strong entity is due, not weak.

`GET /weak-areas` accepts entity type, classification, limit, and offset. Its
repository uses an ownership-filtered `LEFT JOIN`, so owned entities without
mastery remain visible as insufficient evidence. Classification predicates,
classification-specific ordering, and count all run in PostgreSQL before
pagination. This avoids the common bug where an arbitrary page is fetched and
then filtered in Python. The deterministic entity-ID tie-breaker makes adjacent
pages stable, and one joined query avoids N+1 reads.

### Item-driven SMART selection

SMART uses learning-item mastery as its allocation signal. Label mastery remains
valuable explanatory data in `/weak-areas`, but combining item and label scores
would count the same submitted answers twice. Candidate questions use the same
eligibility predicate as RANDOM and LABEL: they must belong to an authenticated
user's item and contain a complete, safe four-option question.

Eligible candidates are grouped by item. Tier 1 contains demonstrated-weakness
items, Tier 2 contains sufficiently evidenced items due for review, and Tier 3
contains exploration/fill material. Questions inside each item are shuffled
through an injectable randomizer. Tier 1 and then Tier 2 are selected in ranked
round-robin order. A soft per-item cap of half the requested quiz prevents one
large item from dominating while alternatives exist. Remaining places go to the
least-selected eligible item; the cap relaxes only after alternatives are
exhausted. The final question order is shuffled once and persisted as immutable
session snapshots, so resume never resamples.

If no Tier 1 or Tier 2 item has an eligible question, SMART delegates to the
existing RANDOM selection and records `requested_strategy=SMART` with
`strategy_used=RANDOM`. If even one actionable priority question is included,
the session records SMART/SMART, even when exploration questions fill the rest.
This makes partial personalization unambiguous. If the entire eligible bank is
too small, creation returns the existing shortage response and persists nothing.
`allow_ai_generation=true` remains request-compatible but does not invoke AI in
this phase.

### Phase 4 request flows

```text
GET /weak-areas
→ authentication dependency
→ thin mastery router
→ WeakAreaService captures one UTC as_of
→ repository applies ownership + classification + ordering + pagination in SQL
→ service maps evidence reasons and Decimal accuracy
→ answer-free response
```

```text
POST /revision-sessions { quiz_type: SMART }
→ authentication dependency
→ existing revision router
→ RevisionSessionService dispatches SMART
→ repository loads owned eligible candidates and item mastery in one query
→ pure SMART selector prioritizes, balances, deduplicates, and shuffles
→ existing owned-question revalidation and immutable snapshot persistence
→ one service-owned commit
→ answer-safe session response
```

### Phase 4 module and function mapping

| Module or symbol | Responsibility |
|---|---|
| `mastery.weak_areas.classify_weak_area` | Pure evidence precedence and reason selection |
| `mastery.repository.list_owned_weak_areas` | SQL ownership, LEFT JOIN, filtering, ordering, count, and pagination |
| `WeakAreaService.list` | One request timestamp, mapping, accuracy, and response metadata |
| `mastery.router` | Authenticated `/weak-areas` HTTP contract |
| `revisions.repository.eligible_question_filters` | Shared RANDOM/LABEL/SMART bank eligibility |
| `revisions.repository.list_owned_eligible_smart_candidates` | Owned candidates plus optional item mastery in one query |
| `smart_selection.candidate_tier` | Pure item-evidence tier assignment |
| `smart_selection.select_smart_question_ids` | Balanced selection, cap behavior, fallback, and final shuffle |
| `RevisionSessionService._create_smart` | Shortage handling and reuse of snapshot transaction workflow |

### Deliberate limits and verification boundary

Phase 4 does not avoid recently seen questions, scope SMART by labels, decay
scores, generate a shortage with AI, or change mastery. Those policies need
separate evidence and approval. Label mastery remains explanatory rather than an
allocation input.

Pure classification, balancing, fallback, validation, and secrecy tests run
offline. PostgreSQL tests cover the actual LEFT JOIN predicates, SQL ordering and
pagination, ownership isolation, new strategy constraints, persistence, resume,
submission, and result behavior. They remain pending until a safe dedicated
`TEST_DATABASE_URL` is available. Migration `0005` changes only the two strategy
checks and refuses downgrade when SMART history exists; it must still be tested
against PostgreSQL before deployment.

Two offline-verification mistakes were caught and corrected. The first unit and
integration weak-area test files had the same basename, so pytest imported one
as the other; the integration file was renamed to keep test-module identities
unique. A PowerShell one-line schema check also expanded `$defs` as a shell
variable and produced a false `KeyError`; the corrected check reads the OpenAPI
components directly. The lesson is to distinguish test-harness failures from
application defects, then rerun the final checks rather than relying on stale
results.

## 18. Database-protection follow-up and legacy adoption

Migration `0006` makes four existing database protections explicit in both the
current ORM and the versioned schema. A key point must belong to a learning item,
deleting that item cascades to its key points, deleting a user cascades to that
user's authentication sessions, and direct SQL session inserts default
`is_active` to true. The Python default remains for ORM-created sessions, while
the column deliberately remains nullable so an explicit `NULL` is not silently
rewritten.

These rules belong in PostgreSQL as well as service code. The learning-item
service currently deletes key points explicitly, but a database cascade also
protects direct SQL, maintenance commands, and future deletion paths. User
sessions have no useful lifetime after their owning user disappears, so their
foreign key follows the same ownership rule.

The upgrade refuses before mutation when a key point has no parent reference,
when a key-point or user-session reference is orphaned, or when the expected
`0005` foreign keys are missing or structurally different. It does not delete an
invalid row or invent a parent. The downgrade only removes these protections: it
restores nullable key-point references, `NO ACTION` foreign keys, and no
server-side active default without deleting rows or changing IDs.

### Adoption sequence and transaction boundary

The existing development database predates Alembic. To adopt it safely, a
restored rehearsal copy is reconciled to the exact `0001` schema, verified, and
then stamped. That exact baseline temporarily has weaker key-point/session
protections. Application writers must remain disabled while the rehearsal or
eventual development target advances through `0002`–`0005` and immediately to
`0006`. Writes resume only after nullability, both cascade actions, the active
default, retained IDs, and aggregate row counts are verified.

This sequence is not one transaction. Reconciliation, stamping, and each
stepwise Alembic command are separate recovery boundaries. PostgreSQL can roll
back the currently failing migration, but it cannot roll back earlier commands
that already committed. After any uncertain connection failure, inspect the
recorded revision and schema before retrying; restore the verified backup when a
safe forward recovery cannot be demonstrated.

Destructive migration tests remain restricted to the separately guarded
`MIGRATION_TEST_DATABASE_URL`, and application integration tests remain on
`TEST_DATABASE_URL`. Neither suite may target the adoption-rehearsal copy. That
copy receives read-only preservation checks plus separately reviewed smoke tests
that create, exercise, and remove only explicitly identified rehearsal records.

## 19. One-time legacy-schema reconciliation tooling

The development schema was created before Alembic and is close to, but not
identical to, migration `0001`. It must not be stamped merely because its table
names look familiar. The rehearsal-only command
`scripts/reconcile_legacy_schema_to_0001.py` accepts only
`ADOPTION_REHEARSAL_DATABASE_URL`; it never selects the application or either
automated-test database as a fallback. It also refuses Neon pooler hosts because
session-level advisory locks and transaction state must remain on one direct
PostgreSQL connection for the complete operation.

The workflow has three explicit stages:

1. `--dry-run` opens a read-only repeatable-read transaction, obtains the
   adoption advisory lock, verifies the exact 13-table legacy shape and all 35
   reviewed differences, and writes a local preservation snapshot. The snapshot
   contains aggregate row counts, hashes of ordered primary-key IDs, and sequence
   ownership/state. It contains no records, credentials, hostname, or database
   name.
2. `--apply --confirm-rehearsal-reconciliation` is schema-destructive and is
   permitted only for the isolated rehearsal branch during exclusive write
   downtime. It locks all 13 tables, reruns every schema/data/orphan/duplicate
   guard, verifies the dry-run snapshot is still current, and applies the exact
   reconciliation in one PostgreSQL transaction. It does not stamp Alembic or
   run a migration.
3. `scripts/verify_legacy_schema_reconciliation.py` independently reads the
   reconciled rehearsal schema. It requires zero structural and naming
   differences from `0001`, no upgrade-name blockers, no `alembic_version`
   table, and preservation of row counts, ordered-ID signatures, sequence
   ownership, and sequence state.

The reconciliation temporarily adopts the weaker historical `0001` definition:
key-point ownership becomes nullable, the key-point and user-session foreign
keys become `NO ACTION`, and the session active server default is removed. It
also performs only the reported mechanical changes: two enum conversions, the
question answer type normalization, removal of two empty attempt columns and one
extra uniqueness constraint, removal of six mastery defaults, creation of the
12 baseline ID indexes, and three constraint renames. It never deletes retained
rows, recreates application tables, or changes primary-key IDs. Migration
`0006` restores the four approved protections after the rehearsal has advanced
through `0002`-`0005`.

### Recovery and approval boundaries

The reconciliation DDL is atomic by itself: an exception inside its transaction
rolls back every reconciliation statement. The broader adoption is not atomic.
Reconciliation, verification, stamping `0001`, and each later Alembic upgrade
are separate committed boundaries. Keep the verified database backup and the
isolated branch until retained-data checks and the final `0006` protections have
all passed. If reconciliation fails, inspect the sanitized stage/code and rerun
the read-only preflight after correcting the cause. If a later stamp or migration
fails, inspect the actual revision and schema before deciding whether to resume
forward or restore the rehearsal copy.

No application writer may run between the temporary `0001` reconciliation and
verification of `0006`. Destructive pytest fixtures remain limited to their two
dedicated test databases; they must never be pointed at the preservation
rehearsal. Running the dry-run, apply, verifier, stamp, or migrations requires a
separate operational approval after the commands and target are reviewed.
