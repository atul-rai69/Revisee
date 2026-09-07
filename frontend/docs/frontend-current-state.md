# Revisee frontend: current state

Audit date: 2026-09-05; revision-flow update: 2026-09-06
Repository checkpoint: branch `feature/quiz-frontend`, commit `c2f2d12`

This document records what the Angular application actually does at the audit
checkpoint. “Verified” statements come from source inspection, generated
FastAPI OpenAPI metadata, or commands run during the audit. Recommendations are
kept in a separate section. The revision-flow sections below describe the
uncommitted Phase 1 implementation currently in the working tree.

## Dynamic learning-item resources and question bank (2026-09-06)

The owned learning-item detail now derives image, PDF, Topic, key-point, and
question presentation entirely from `GET /learning-item/{item_id}`. Media URLs
are restricted to HTTPS on the current Cloudinary delivery host; PDFs are
embedded as readable previews and retain an
explicit open-in-new-tab action. Empty media/content sections are honest; the
old sample resources, notes, images, and hard-coded question count are gone.

The guarded `/app/learning-items/:id/questions` page lists the complete returned
question bank with difficulty and expected time. Correctness and explanations
are revealed only when the learner requests them. Both this page and item
detail activate the authenticated `POST /generate` contract using
`{learning_item_id, title, description}`. Because the response contains only a
message, the UI reloads the canonical owned detail after success and prevents
duplicate generation requests while one is active.

Verification for this increment: 8 focused tests and the complete 72-test
frontend suite passed, application and test TypeScript checks passed, and the
backend OpenAPI contract smoke passed. Production compilation succeeded. Its
configured gate remains blocked by the pre-existing 1.18 MB initial bundle and
NewItem's 11.26 kB stylesheet; splitting the learning-item media styles removed
the learning-item detail's former 8 kB error.

## Dashboard and login redesign implemented on 2026-09-06

The login route now uses a responsive split card built from real HTML and the
checked-in `/assets/login/` package. The reactive form preserves the backend's
`{username, password}` request, token storage, and post-login navigation.
Unsupported registration, password recovery, remember-me, and social-login
controls are absent. Required validation, password visibility, safe credential
and network feedback, local loading, and duplicate-submit prevention are real.

The visual panel layers a scalable background, transparent generic learning
art, an HTML headline, and an optional decorative canvas. The canvas is
noninteractive, hidden on mobile, device-pixel-ratio and particle-count capped,
delta-time driven, paused with the document, torn down on destruction, and
static under reduced motion. Login continues to work without canvas support.

The Dashboard now renders only data from `/dashboard/summary`,
`/dashboard/learning-items-summary`, and `/labels`. Fake review totals,
progress percentages, recently viewed examples, remote sample imagery, and
sample sessions were removed. The three data sources load independently and
have honest skeleton, error/retry, and empty states. Search covers the currently
loaded learning items. Continue Revision is intentionally absent because there
is no session-list endpoint or validated recent-session client mechanism.

Final redesign verification: 37 focused tests passed, the complete suite passed
66/66 tests across 29 files, application and test TypeScript compilations
passed, and the development build passed. Production compilation succeeded but
the configured gate still failed on the 1.16 MB initial bundle and the unchanged
NewItem (11.26 kB) and learning-item detail (10.48 kB) styles. Dashboard's two
style files and Login remain below the 8 kB component-style error budget; no
budget was increased.

## Revision experience implemented on 2026-09-06

The guarded application now has three lazy routes: `/app/revise`,
`/app/revision-sessions/:sessionId`, and
`/app/revision-sessions/:sessionId/result`. The setup page creates RANDOM,
LABEL (shown as Topic), and SMART sessions using strict DTOs. The runner loads
the server-persisted order and keys draft answers and measured time by immutable
`session_question_id`. It submits one complete answer set; the backend remains
the grading authority. The result page reloads the canonical completed result
and is the only revision page whose types and UI contain correct answers,
explanations, correctness, or mastery deltas.

Loading is deliberately split: blocking application HTTP keeps the existing
reference-counted global notebook loader, while Topic loading, creation,
session loading, submission, and result loading use local states. Toasts expose
appropriate `status`/`alert` live-region semantics, and exit and final
submission use a keyboard-aware confirmation dialog. The existing sidebar adds
Revise, uses Topics in product copy, and becomes a bottom bar on small screens.

## Verified technical baseline

- Angular 21.1 standalone-component application, TypeScript 5.9 in strict mode.
- RxJS 7.8, Bootstrap 5.3, TipTap 3.23, Phosphor icons, and Vitest 4.1.
- There is no NgModule-based application module. `bootstrapApplication()` loads
  `App` with providers from `app.config.ts`.
- `HttpClient` is configured with functional loader and authentication
  interceptors. Routes use a functional authentication guard.
- The API base URL is a compile-time value in
  `src/environments/environment.ts`; only one environment file exists.
- API/domain interfaces are declared inside individual services and page files.
  There is no shared API-model or feature-state layer.
- Components subscribe directly to service observables. There is no store,
  resolver, facade, or server-state caching layer.

## Routes and pages

| Browser route | Component | Guarded | Verified state |
|---|---|---:|---|
| `/` | `Login` | No | Accessible reactive login preserves the real username/password contract and has no unsupported account actions. |
| `/app` | `AppLayout` | Yes | Parent shell only. It has no default child redirect, so the content area is blank. |
| `/app/dashboard` | `Dashboard` | Yes | Honest Home/My Learning surface using real summary, Topic, and learning-item data with search and local states. |
| `/app/new-item` | `NewItem` | Yes | Creates a learning item with HTML notes, selected Topics, images, and PDFs. Its search control is now isolated correctly from the parent reactive form. |
| `/app/labels` | `Labels` | Yes | Lists, creates, and updates backend labels. This concept should be called “Topics” in user-facing UI. Search, sort, pagination, and delete are not wired. |
| `/app/learning-items/:id` | `LearningItemView` | Yes | Loads owned details, real counts, images, embedded PDFs, theory, key points, and a three-question bank preview with honest states. |
| `/app/learning-items/:id/questions` | `LearningItemQuestions` | Yes | Lists the complete returned question bank, supports deliberate answer/explanation reveal, and can generate then refresh more revision content. |
| `/app/revise` | `Revise` | Yes | Creates RANDOM, Topic/LABEL, or SMART stored-question sessions with strategy-specific reactive controls. |
| `/app/revision-sessions/:sessionId` | `RevisionSession` | Yes | Loads/resumes persisted answer-safe questions, records in-memory answers/timing, and submits the complete set. |
| `/app/revision-sessions/:sessionId/result` | `RevisionResult` | Yes | Loads the canonical completed result and presents grading, explanations, timing, and mastery deltas. |
| `/app/playground` | `Playground` | Yes | Development animation experiment, absent from production navigation. |
| `/app/canvas` | `Canvas` | Yes | Development canvas experiment, absent from production navigation. |

`DesignPreview` is a TipTap/design-system experiment with a test but no route.
There is no wildcard/404 route, no `/app` default redirect, and no route for a
weak area, registration, item library, real analytics, or settings page.

## Layout and navigation

`AppLayout` renders the existing sidebar and scrollable content area. The
sidebar now displays Home, My Learning, Revise, and Topics, and becomes a bottom
navigation bar below 720 px.

Verified navigation gaps:

- My Learning links to the real dashboard library section; a dedicated paged
  library route remains future work.
- Playground and Canvas still exist as development routes, but are no longer
  presented as Analytics or Settings navigation.
- The logo points to the unguarded login route.
- The notification and profile controls are visual only; the fake remote avatar
  was replaced by a neutral account icon.
- There is no navigation entry or page for weak areas.

## Services and API usage

| Service | Responsibility | Observed quality/state |
|---|---|---|
| `AuthService` | Login, logout, local token storage, JWT-expiry decoding | Active. Responses are typed; token uses `localStorage`. |
| `DashboardService` | Summary and learning-item cards | Active and typed. |
| `LabelService` | Backend Topic (`label`) list/create/update | Active and typed at the API boundary. |
| `LearningItem` service | Create, detail, delete, manual generation | Active and strictly typed for these contracts. Generation includes the owned item ID and consumes the backend's message-only response. The legacy service class name remains awkward. |
| `LoaderService` | Reference-counted global request state | Active through the loader interceptor. |
| `ToasterService` | Signal-backed transient notifications | Active and shared. |
| `RevisionSessionService` | Create, resume, submit, and result requests | Active, strictly typed, and uses the configured API base URL. |
| `Login` service | Posts to `/auth/login` | Unused dead/obsolete service; the backend path is `/login`. |

There is no frontend service for weak areas or public question statistics.
Mastery is presented only through the completed-result contract.

## Authentication and HTTP behavior

The login page sends `{username, password}` to `/login`, stores
`response.access_token`, and navigates to `/app/dashboard`. `authGuard` checks
that a token exists and performs a client-side expiry check. `authInterceptor`
adds `Authorization: Bearer ...` and clears the token/redirects on most 401
responses. `loaderInterceptor` uses a counter, so parallel requests keep the
global overlay visible until all requests finish.

Important limitations:

- A decoded JWT is not proof that the token is valid; the backend remains the
  security authority.
- `localStorage` tokens are readable by JavaScript, so XSS would expose them.
- The interceptor attaches the token to every Angular `HttpClient` request,
  without checking that the destination is the configured API origin.
- A failed logout leaves the token in storage.
- There is no registration UI even though `/register` exists.
- The legacy unused `Login` service targets nonexistent `/auth/login`.

## Page behavior and states

### Login

Current: reactive required-field validation, exact username/password submission,
password visibility, typed response, token storage, navigation, safe error copy,
local loading, and duplicate prevention. Unsupported account actions are
deliberately omitted rather than displayed as inert links.

### Dashboard

Current: real username/counts, owned Topics, and returned learning-item fields;
loaded-item search; independent skeleton/error/retry/empty states; and real
revision, Topic, creation, open, and delete actions. Unsupported review,
mastery, progress, recently viewed, analytics, and session history are absent.

### Learning-item creation

Working intent: reactive title/description form, TipTap HTML, Topic selection,
image previews, PDF selection, multipart submission, reset, and toasts.

Confirmed defects/gaps:

- `labelSearch` remains template-driven but is explicitly standalone, avoiding
  accidental registration with the parent reactive form.
- Topic search does not filter the displayed list.
- Save Draft and underline are inert.
- Displayed image/PDF size and type promises are not enforced in this code.
- Image object URLs are revoked on successful reset, but not on component
  destruction or individual removal.
- Topic-load errors have no handler.
- There is no double-submit prevention or local submission status.

### Topics

Backend list/create/update are wired with form validation and toasts. The search
field, alphabetical sort control, pagination controls, and delete button are
visual placeholders. There is no backend delete-label endpoint at this
checkpoint, so delete needs a product/API decision rather than frontend wiring
alone.

### Learning-item detail

Real API data populates title, notes HTML, timestamps, media counts, theory, key
points, questions, Topics, images, and PDFs. Loading, concealed-not-found,
retry, no-image, no-PDF, no-key-point, no-theory, and no-question states are
explicit. The item page previews three questions and links to a complete bank.
Correct answers in these study-bank views originate from the detail endpoint;
the answer-safe revision-session DTOs and quiz runner remain separate.

Remaining gaps: there is no backend edit endpoint; the detail screen does not
offer edit or delete actions; PDF embedding depends on the browser/provider's
inline-PDF support; and the backend regeneration operation also replaces theory
and appends key points, despite the action's learner-facing focus on generating
more questions.

### Experimental pages

`Playground`, `Canvas`, and `DesignPreview` are learning/design experiments, not
product capabilities. Playground and Canvas start perpetual animation-frame
loops and do not cancel them on destruction. Canvas assumes a 2D context even
where one is unavailable. They should not stand in for Analytics or Settings.

## Styling and responsive behavior

The project has useful color, spacing, radius, shadow, typography, transition,
theme, and reusable-component tokens. Bootstrap utilities and custom CSS are
used together. Dashboard, new-item, learning-item detail, and toast styles
contain some media queries.

Verified limitations:

- The shell/sidebar now has a mobile bottom-navigation breakpoint; older page
  layouts still vary in responsive quality.
- Several global style files are empty (`breakpoints`, reset, typography base,
  z-index, and multiple utility files).
- `light-theme.css` is imported both from `styles.css` and `globals.css`.
- Component styles are large: new-item about 922 lines, learning-item view 624,
  dashboard 500, Topics 447, and toast 363.
- Phosphor is a package dependency, but icon CSS is fetched from two public CDN
  links in `index.html`.
- Some source strings display encoding artifacts such as `â€™` and `â†’`.
- The production build currently exceeds configured bundle/style budgets.

## Loading, errors, empty states, and success feedback

- Global loading: reference-counted for blocking requests; revision and Topic
  page requests use local loaders through an explicit HTTP context.
- Success feedback: implemented for login/logout, Topic mutation, item creation,
  and item deletion.
- Error feedback: partial. Interceptor handles 401/403/network/5xx broadly;
  pages use toasts inconsistently and some only log errors.
- Empty states: implemented for dashboard and item-detail media/content; Topic
  management remains uneven.
- Form validation: present for new-item title/notes, Topic name, and all three
  revision strategies; login validation remains basic.
- Revision pages include dimension-preserving loaders, retryable errors, safe
  concealed-404 copy, and duplicate-action guards. Older pages remain uneven.

## Tests and build status

At the audit checkpoint there were 16 `*.spec.ts` files and 17 discovered tests. Most asserted only that a
component, service, guard function, or interceptor function exists. There are no
HTTP contract tests, router tests, form behavior tests, authentication behavior
tests, revision tests, accessibility tests, or end-to-end setup. Dashboard and
learning-item detail have no spec files. No coverage threshold or coverage
report is configured, so a meaningful percentage cannot be claimed.

Command results from 2026-09-05:

- `npm.cmd test -- --watch=false`: **failed** — 12 tests passed and 5 failed;
  Vitest also reported 2 unhandled errors. Failures cover the obsolete app title
  assertion, missing router providers in layout/sidebar tests, the NewItem
  reactive/template-form conflict, and Playground change detection. Unhandled
  errors came from Canvas lacking a JSDOM canvas context and a real `/labels`
  network request escaping a test.
- `npm.cmd run build`: **failed configured budgets after successful
  compilation**. Initial output was 1.15 MB against a 1 MB error budget.
  Dashboard CSS was 8.48 kB, new-item CSS 11.26 kB, and learning-item-view CSS
  10.48 kB against 8 kB component-style error budgets. Labels CSS produced a
  warning at 5.35 kB.

The revision phase adds HTTP-contract, route, form mapping, shortage, answer
secrecy, navigation, timing, duplicate-request, result, loader, toast, error,
and dialog tests. Final command results are recorded in the implementation
journal and handoff report.

Verification on 2026-09-06: the focused feature run passed 25/25 tests, the
complete suite passed 43/43 tests, TypeScript application/spec compilation
passed, and the development build passed. The production compiler completed,
but the configured budget gate still failed at 1.16 MB initial output and on
the pre-existing Dashboard (8.48 kB), NewItem (11.26 kB), and learning-item
detail (10.48 kB) styles. New revision styles produced warnings but remained
below the 8 kB error threshold. No budget was raised.

The first sandboxed test attempt could not resolve project files because of the
execution sandbox; the rerun with normal project access produced the real test
results above.

## Duplicated, dead, or suspicious code

- Unused `core/services/login.ts` duplicates part of `AuthService` with the
  wrong endpoint.
- Learning-item detail no longer retains sample media, notes, or questions.
- Root `App.title` and its generated starter test remain, while `app.html` has
  no title heading.
- DesignPreview is unreachable; Canvas and Playground remain direct development
  routes but are absent from production navigation.
- NewItem contains commented-out alternatives and imports `OnDestroy` without
  declaring it in the class contract.
- Many action buttons have no handlers.
- Several API returns and page mappings use `any`, hiding contract drift.

## Recommendations (not current behavior)

1. Build the `/weak-areas` frontend so existing mastery classifications become
   visible and actionable without inventing analytics.
2. Add a dedicated paged learning library; keep item and Topic creation contextual.
3. Decide whether question-only manual generation needs a dedicated backend
   endpoint instead of the current full revision-content regeneration contract.
4. Scope auth headers to the configured API origin and review token storage with
   the backend security model.
5. Remove development-only routes from production bundles and address the
   initial/NewItem/item-detail build-budget debt without raising limits.
