# Frontend implementation journal

## 2026-09-07 — Learning-item async rendering repair

### Objective

Fix the detail and question-bank pages remaining on their loading views after
real asynchronous HTTP responses, despite passing synchronous mocked tests.

### Decisions and behavior changed

- Move page-visible loading, error, item, media, question, and generation state
  to Angular signals so Angular 21 schedules zoneless rendering after HTTP
  callbacks and `finalize()`.
- Normalize the runtime `response.data` object at the service boundary. Nullable
  or missing lists become empty lists before templates iterate over them, while
  malformed response envelopes remain Observable errors.
- Keep one `finalize()` per request as the authoritative release path. HTTP
  errors, mapping errors, completion, and cancellation therefore cannot strand
  the local loader.
- Build PDF resources before publishing the item signal and keep URL parsing
  guarded. Invalid or non-Cloudinary URLs cannot block the rest of the page.

### Tests and verification

Added asynchronous Subject-based component regressions, nullable-collection,
invalid-route, request-failure, malformed-envelope, and unsafe-PDF cases. The
focused service/page/routing suite passed 19/19; the complete frontend suite
passed 83/83; application and test TypeScript checks passed; and the development
build passed. A headless-browser route smoke test rendered both pages with an
asynchronous contract-accurate response, removed both loaders, and reported no
runtime exceptions. The production build still fails the already-recorded
initial-bundle and NewItem stylesheet budgets.

### Lesson and interview explanation

Synchronous `of(...)` fixtures can hide UI-notification defects. “I reproduced
the component with a truly asynchronous response, moved externally completed
state to signals, normalized API collections at the boundary, and proved every
terminal path releases loading through `finalize()`.”

---

## 2026-09-06 — Dynamic PDFs, question bank, and generation repair

### Objective

Make owned learning-item resources truthful and usable: display attached PDFs,
offer a complete stored-question view, and activate the existing authenticated
generation endpoint.

### Decisions

- Treat `GET /learning-item/{item_id}` as the canonical source for every media,
  count, theory, key-point, and question state; remove all sample item content.
- Permit only HTTPS URLs from the current Cloudinary delivery host before
  rendering. Sandboxed PDF previews retain a normal new-tab link because inline
  support varies by browser and response headers.
- Keep the question-bank study view distinct from answer-safe revision-session
  DTOs. Answers/explanations are hidden until explicitly revealed on the bank.
- Match `/generate` exactly with `{learning_item_id,title,description}` and its
  message-only response, then reload detail. A local busy flag prevents duplicate
  paid/provider actions.

### Files changed

Strengthened the learning-item service DTOs, rebuilt the detail mapping, added
the guarded `LearningItemQuestions` page and route, added focused HTTP/component
tests, and updated the frontend project record. Backend and dependencies were
not changed.

### Behavior added or changed

PDFs are now visible and openable, counts and question previews are dynamic,
empty/error/loading states are explicit, and all stored questions can be read
from `/app/learning-items/:id/questions`. Successful generation refreshes both
the detail or question-bank view from the backend.

### Tests

Focused tests cover the detail URL, exact generation body, unsafe URL filtering,
dynamic PDF rendering, the all-question route, deliberate answer reveal,
duplicate generation prevention, refresh-after-success, and sanitized failure
feedback. The focused run passed 8/8 and the complete frontend suite passed
72/72. Application/test TypeScript and the backend OpenAPI contract smoke
passed. Production compilation succeeded; the gate still fails only on the
pre-existing initial-bundle and NewItem stylesheet errors. Splitting the item
media styles removed this page's former 8 kB error without raising a budget.

### Problems and lessons learned

The old frontend called the correct URL but still violated the contract by
omitting ownership context and expecting inline theory. Typed DTOs revealed the
nullable media fields and additional question metadata. Canonical reloads are
safer than synthesizing partial state from a mutation acknowledgement.

### Interview explanation

“I replaced a static item-detail prototype with a typed, owned API projection.
I validated renderable media schemes, gave PDFs an accessible fallback, created
a focused question-bank route, and repaired AI generation by matching the exact
request and message-only response before reloading canonical data.”

---

Use this journal after meaningful feature changes or architectural decisions,
not after every formatting edit. Entries should distinguish observed facts from
intent and include failures when they teach something useful.

## 2026-09-06 — Honest Dashboard and accessible Login redesign

### Objective

Replace the prototype Dashboard and dated login composition with final Revisee
surfaces that use real backend behavior, the existing shell/design tokens, and
the approved local asset package.

### Decisions

- Preserve the exact username/password login contract, token key, guard,
  interceptor, and successful navigation. The form is real reactive HTML;
  imagery remains decorative and cannot control authentication.
- Layer the login visual as scalable background, optional canvas, transparent
  generic illustration, and HTML headline. Text is never baked into a bitmap.
- Keep the canvas bounded: delta-time movement, clamped frame gaps and
  device-pixel ratio, area-based particle caps, static reduced motion, mobile
  suspension, visibility pause, and full lifecycle cleanup.
- Treat summary, Topics, and learning material as independent Dashboard
  sections. Local skeletons and retry states avoid replacing the whole shell.
- Remove unsupported prototype metrics rather than implying data the backend
  does not provide. Continue Revision is absent without a session-list or safe
  validated recent-session mechanism.

### Files changed

Redesigned the Login and Dashboard components and their focused tests; added
`KnowledgeParticles`; typed auth, Dashboard, and Topic service responses;
adjusted login interceptor feedback and sidebar My Learning navigation; moved
the supplied package to `public/assets/login/`; and updated all frontend docs.
No backend, dependency, package, lock, Angular configuration, or environment
file was changed.

### Behavior added or changed

Login now provides required validation, show/hide password, accessible local
loading, safe credential/network failures, and duplicate-request prevention.
The Dashboard binds username, item/Topic totals, login-date count, owned Topics,
and returned item summary fields. It supports loaded-item search, honest local
states, real navigation, and safe image fallback. Dashboard revision buttons
preselect RANDOM or LABEL on the existing setup route through a validated query
parameter; setup logic remains in the Revise page.

### Tests

Focused service/component tests use fake services or Angular's HTTP test
controller; no backend is contacted. They cover the login payload, validation,
password visibility, success/error/loading, duplicate blocking, Dashboard
binding/search/states/navigation, particle caps/reduced motion/cleanup, loader,
toaster, interceptor, sidebar, and Revise query mapping. The initial focused
run found that jsdom lacked `matchMedia`; the component was hardened with a
safe optional-browser-API fallback. The final focused run passed 37/37 tests;
the full suite passed 66/66 across 29 files; app and spec TypeScript checks and
the development build passed. Production compilation succeeded, then the
configured gate failed only on the 1.16 MB initial bundle and the pre-existing
NewItem (11.26 kB) and learning-item detail (10.48 kB) component styles. The
Dashboard and Login introduced no 8 kB component-style error, and no budget was
raised.

### Problems

The interrupted work had a complete Dashboard template but no replacement
stylesheet. The login network/server path could also produce both page feedback
and a global interceptor toast. Both were corrected without changing shared API
contracts. CSS budgets remain a measured constraint and are not increased.

### Lessons learned

Global and local loaders have different scopes: independent Dashboard panels
should not block the shell. Canvas is appropriate for many tiny dynamic marks,
while supplied SVG/PNG assets remain crisp authored layers. Optional visual APIs
must fail open so authentication remains usable. `requestAnimationFrame`
movement must use elapsed time because frame rate is not constant. Device pixel
ratio improves sharpness but needs a cap to avoid expensive backing buffers.

### Interview explanation

“I replaced fake dashboard analytics with three typed, independently loaded
backend sources and designed honest empty/error states. For login I kept a
semantic reactive form above an optional layered visual system. A bounded
canvas adds calm motion, honors reduced motion and page visibility, and cleans
up observers, listeners, and frames. Contract and component tests prove the
redesign did not change authentication or the revision workflow.”

---

## 2026-09-06 — Complete revision-session experience

### Objective

Expose the backend's stored-question RANDOM, LABEL, and SMART lifecycle from
setup through resume, one-shot submission, and canonical completed results.

### Decisions

- Keep product language as Topics while sending backend label IDs.
- Use discriminated request DTOs and separate answer-safe session DTOs from
  answer-bearing completed-result DTOs.
- Keep route-local state in signals and maps keyed by immutable
  `session_question_id`; a global store is not justified for this flow.
- Measure time per viewed question, cap it at the backend's 3600-second bound,
  and let the backend calculate correctness.
- Keep unsent answers only in memory and warn on exit. Never claim auto-save.
- Use global loading only for blocking work and local loaders within revision
  pages so the shell stays stable.

### Files changed

Added revision contracts, error mapping, `RevisionSessionService`, setup,
runner, result pages, confirmation dialog, and focused tests. Extended routing,
sidebar, responsive shell, loader/toaster behavior, LabelService's optional
local-loading context, and documentation. No backend or dependency changed.

### Behavior added or changed

`/app/revise` creates strategy-specific sessions. The runner restores persisted
question order, times and selects by immutable ID, confirms exit/submission,
prevents duplicates, and submits a complete payload. Results are fetched from
their canonical endpoint and show correct answers only after completion.
SMART-to-RANDOM is reported as valid fallback behavior. Known backend failures
become concise, non-disclosing guidance.

### Tests

HTTP tests assert URLs, verbs, and bodies. Component tests cover mapping,
validation, shortage handling, ordering, answer secrecy, timing, navigation,
complete-answer enforcement, duplicate actions, redirects, results, and
dialogs. Loader/toast tests cover reference counting and accessible roles.
Final results: focused feature tests 25/25 passed; full suite 43/43 passed;
application and spec TypeScript checks passed; development build passed.
Production compilation completed but its budget gate failed on the 1.16 MB
initial output and the same three oversized legacy component styles identified
during the audit. The new revision styles remained below the 8 kB error limit.

### Problems

The baseline suite had stale starter assertions, missing router providers, an
escaped Topic request, a mixed form-control error, and uncontrolled experimental
animation/canvas APIs. Those harness issues were minimally stabilized.
Production compilation succeeds, but the final budget gate remains blocked by
pre-existing initial bundle and old Dashboard/NewItem/item-detail CSS sizes;
limits were not silently raised.

### Lessons learned

Global and local loaders solve different problems. A request counter prevents
one completed concurrent request from hiding another. Inline errors retain page
context, toasts communicate brief outcomes, and dialogs guard irreversible
submission or loss of draft state. RxJS `finalize` releases busy state on both
success and failure. Reduced-motion CSS stops decoration, not status text.

### Interview explanation

“I implemented a typed Angular vertical slice over existing FastAPI contracts.
The browser stores draft choices by immutable session-question ID, while the
server owns grading and atomic mastery updates. Lifecycle-specific DTOs prevent
answer leakage, canonical GETs make resume/results stable, and HTTP/component
tests verify the contract without a real backend.”

---

## 2026-09-05 — Baseline frontend audit

### Objective

Record the real Angular/frontend state and compare it with the modular FastAPI
backend before starting the quiz UI.

### Decisions

- Use **Topics** as the product term while acknowledging backend `label` names.
- Prioritize the complete revision loop before analytics.
- Treat item/Topic creation as contextual actions rather than primary
  navigation.
- Do not describe backend-only capability as frontend functionality.

### Files changed

Documentation only under `frontend/docs/`. No application, backend,
configuration, dependency, or UI behavior changed.

### Behavior found

- Login/logout, basic dashboard reads, Topic list/create/update, item
  create/detail/delete, multipart media upload, global loader, and toasts exist.
- Dashboard/detail contain prototype data and inactive controls.
- Revision sessions, submission/results, mastery presentation, and weak areas
  are absent.
- Manual `/generate` integration is incompatible with the current backend.

### Tests and build

- Unit run: 17 tests discovered; 12 passed, 5 failed, with 2 unhandled errors.
- Production build: compilation succeeded, but configured bundle and component
  style budgets failed.
- No backend, database, or external provider was contacted.

### Problems discovered

- NewItem mixes `ngModel` with a parent reactive form incorrectly.
- Layout/sidebar tests lack router providers.
- App starter assertion is obsolete.
- Playground and Canvas animation behavior is unsafe in tests and is not torn
  down.
- A component test made an unmocked `/labels` request.
- CSS/bundle size exceeds production budgets.

### Lessons learned

Files named `*.spec.ts` do not imply behavioral protection. Tests must control
router/HTTP/browser dependencies and assert contracts that matter. Likewise,
polished prototype panels should not be mistaken for working product features.

### Interview explanation

“I audited routes, API services, UI states, test behavior, and the backend
OpenAPI contract before adding the quiz flow. That exposed a broken generation
contract, prototype-only analytics, weak tests, and missing revision pages. I
used the findings to prioritize an end-to-end revision slice and to separate
verified capabilities from roadmap ideas.”

---

## Entry template

## YYYY-MM-DD — Short change title

### Objective

What user or engineering outcome was pursued?

### Decisions

What meaningful choices were made, what alternatives were considered, and why
was this approach selected?

### Files changed

List important files or feature areas—not every generated artifact.

### Behavior added or changed

Describe observable behavior, compatibility effects, and anything deliberately
left unchanged.

### Tests

Record exact commands, results, mocked boundaries, and checks not run.

### Problems

What failed or surprised us? How was it diagnosed and corrected? What remains?

### Lessons learned

Capture reusable Angular, API, product, testing, accessibility, or security
lessons.

### Interview explanation

Give a short explanation of the problem, decision, trade-off, and result that a
developer can confidently say aloud.
