# Revisee frontend interview study notes

These notes explain the architecture after the revision-flow implementation.
Quiz setup, runner, and results now exist; weak-area and analytics screens do
not.

## Dashboard data honesty and independent page state

The redesigned Dashboard combines three existing typed sources rather than
inventing a new aggregate. `DashboardService` loads the username/count summary
and learning-item summaries, while `LabelService` loads owned Topics. Each
section has its own loading and failure signal. This keeps an available Topic
list usable if learning-item cards fail and avoids a global spinner for a small
page-local update.

The UI renders only fields supplied by the backend: username, item and Topic
totals, login-date count, item title, Topic strings, first image, media counts,
notes preview, and creation recency. Removing fake progress and recent history
is a product decision as well as a technical one: polished unsupported data
damages trust and makes future API contracts harder to reason about.

## Login layering, reactive forms, and canvas lifecycle

The login card is layered deliberately. SVG supplies a scalable background,
PNG supplies the transparent authored illustration, canvas draws many small
dynamic particles efficiently, and HTML owns all meaningful text and controls.
Keeping the form as HTML preserves keyboard behavior, autocomplete, labels,
validation associations, password-manager support, responsive reflow, and
screen-reader access. A screenshot could provide none of those reliably.

The reactive form owns `username` and `password` validators. Its submit handler
uses a signal as an immediate duplicate-request gate, disables controls during
the observable, and uses `finalize` to restore them on success or failure. The
HTTP shape remains `{username, password}`; a visual redesign is not permission
to rename a backend identifier or alter authentication semantics.

`KnowledgeParticles` starts after its canvas exists, observes its container,
and scales the backing buffer by a capped device-pixel ratio so lines remain
sharp without unbounded GPU or memory cost. Movement multiplies velocity by
elapsed seconds instead of assuming a fixed frame rate; large deltas are
clamped after sleeping tabs. Visibility changes pause and resume the loop.
Destruction cancels the frame, disconnects `ResizeObserver`, and removes
pointer, visibility, media-query, and fallback resize listeners.

Reduced motion renders one static state and starts no continuous loop. Mobile
hides the full illustration field and does not animate an invisible canvas.
The canvas is `aria-hidden`, cannot receive pointer events, and the form remains
usable if canvas or media-query APIs are unavailable.

Interview answer: “I treated animation as optional progressive enhancement.
The authentication surface remains semantic HTML, while a bounded canvas owns
only decoration and has explicit lifecycle, performance, and accessibility
rules.”

## How the Angular application starts

`src/main.ts` calls `bootstrapApplication(App, appConfig)`. This is Angular’s
standalone style: components declare their own imports, and application-wide
providers live in `app.config.ts` instead of an `AppModule`.

`App` is the root composition point. Its template contains the global loader,
toast container, and `router-outlet`. Angular places the component for the
current route inside that outlet.

Interview answer: “Revisee uses standalone Angular components. The root stays
small and composes cross-cutting UI plus the router. That reduces module
ceremony, but it still requires deliberate feature organization as the app
grows.”

## Routing and layouts

`app.routes.ts` maps `/` to Login and protects the `/app` route tree with
`authGuard`. `AppLayout` provides a sidebar and a nested `router-outlet`, so
authenticated pages share one shell.

The guard is useful for navigation UX, but it is not authorization. Users can
alter browser state; the FastAPI backend must—and does—authenticate requests and
enforce resource ownership. The current router lacks a default `/app` child and
a wildcard page, and experimental pages occupy Analytics/Settings navigation.

## Services and dependency injection

Classes marked `@Injectable({providedIn: 'root'})` are single application-level
services. Angular’s dependency injector constructs them and supplies their
dependencies, such as `HttpClient`. Components ask for abstractions such as
`DashboardService` rather than constructing network clients themselves.

Examples:

- `AuthService` owns token-related client behavior and auth API calls.
- `DashboardService`, `LabelService`, and the learning-item service group API
  calls by backend feature.
- `LoaderService` and `ToasterService` expose cross-cutting UI state.
- `RevisionSessionService` owns create, resume, submit, and result HTTP calls;
  the page components own only presentation and route-local orchestration.

Why it helps: dependencies can be replaced with fakes in tests, and components
focus on presentation/orchestration. Current tests do not yet take advantage of
that seam consistently.

## Observables and signals

`HttpClient` returns RxJS `Observable`s. Nothing happens until a component
subscribes. `next` handles a response and `error` handles failure. Interceptors
can transform or observe the same stream; the loader uses `finalize`, which runs
on success, error, or cancellation.

Signals hold synchronous UI state. Dashboard counts, Topic collections, edit
mode, loader count, and toasts use signals. A computed signal derives whether
the loader is visible.

Rule of thumb: use signals for local/current UI state and observables for async
event streams. Convert or compose them intentionally; avoid nested/manual
subscriptions when operators or framework lifecycle helpers give clearer
cleanup. Revisee currently uses direct subscriptions and has no state store,
which is reasonable at this size.

## Guards versus interceptors

The auth guard runs before protected route activation. It checks for a token and
its client-readable expiry, then returns `true` or a redirect `UrlTree`.

The auth interceptor runs for HTTP calls. It attaches the bearer token and
reacts to 401, 403, connection, and server errors. The loader interceptor wraps
every request with reference-counted loading state.

Important distinction: a guard controls navigation; an interceptor controls
HTTP request/response behavior. Neither replaces backend authorization. A good
future correction is to attach credentials only when the request targets the
configured backend origin.

## API integration and DTOs

Angular services translate frontend intent into HTTP calls. DTOs should describe
the wire contract exactly, including nullability and different lifecycle views.
The current code has some useful interfaces but also uses `any` and marks
nullable backend fields as required strings.

The quiz workflow makes DTO separation security-relevant:

- Create/resume questions intentionally exclude correct answers and
  explanations.
- Completed results include those fields.
- Reusing one answer-bearing interface for both could leak answers through UI
  assumptions, fixtures, or accidental rendering.

The repaired `/generate` flow is a practical contract lesson: matching a URL is
not enough. The service sends the required owned learning-item ID with title and
description, consumes the actual message-only response, and then reloads the
canonical detail. That avoids inventing `response.data.theory` and ensures all
new questions/key points are mapped from the backend's source of truth.

## Authentication and token handling

After login, the app stores the access token in `localStorage`. The guard decodes
the JWT payload to read `exp`; decoding is not signature verification. The
backend validates signature, expiry, user, and server-side session.

Trade-off: localStorage survives refresh and is simple, but any successful XSS
can read it. Alternatives such as secure HttpOnly cookies change CSRF/CORS and
backend design, so the right choice must be made across the system rather than
as a frontend-only refactor.

Do not log tokens or login responses. Do not treat hidden UI as authorization.
Always expect 401/404/409/422 responses and show safe user messages.

## Forms

Revisee uses reactive forms for Login, Topic, learning-item creation, and
revision setup. Reactive forms model controls and validators in
TypeScript, which is useful for complex conditional quiz forms.

The Revise setup uses a reactive form because strategy determines valid fields.
RANDOM and SMART expose question count; LABEL exposes Topic IDs and questions
per Topic. A discriminated TypeScript union mirrors this at the HTTP boundary.
NewItem's legacy search control is explicitly standalone so it does not
register accidentally with its reactive parent.

## Revision state, timing, and server-side grading

The route parameter supplies the session ID; the runner calls the backend on
entry instead of trusting navigation state. Questions remain in persisted
order. A `Map` keyed by `session_question_id` stores selected options and time,
so moving through the array cannot attach an answer to the wrong record. The
timer is route-local, capped to the API bound, and stopped on destruction or
successful submission.

Correctness is never calculated in Angular. Client code can be observed and
changed, so the server grades immutable snapshots and updates attempts/mastery
atomically. Results are fetched from their own endpoint, which makes refresh
and direct navigation independent of transient router state.

A synchronous `submitting` guard prevents duplicate submissions and disables
the action. RxJS `finalize` releases that state after success or error, allowing
a safe retry after a network failure.

## Loaders, interceptors, and accessible feedback

The loader interceptor increments a shared count and decrements it in
`finalize`. With two concurrent calls, the overlay remains until both finish.
Revision calls use local loading states because one updating panel should not
replace an otherwise usable application shell.

Toasts use polite `status` live regions for ordinary feedback and assertive
`alert` semantics for errors. Inline errors retain validation/retry context;
dialogs guard exit with unsent answers and final submission. Focus moves into
the dialog and returns afterward, Escape and Tab are handled, and an active
submission cannot dismiss its dialog. `prefers-reduced-motion` rules stop
decorative animation without removing accessible status text.

## Styling and responsive design

The frontend uses CSS custom properties for a small design-token system,
Bootstrap layout/utilities, and component-scoped CSS. Encapsulation prevents
many page selectors from leaking globally, while shared reusable styles live in
global CSS.

The approach is understandable, but large duplicated component styles inflate
the bundle and now violate production budgets. Responsive behavior exists on
some pages but not the application shell. A responsive design is not merely a
few media queries: navigation, touch targets, scroll ownership, empty/error
states, dialogs, and content priority must work at narrow widths.

## Testing

Angular’s configured unit builder runs Vitest with JSDOM. TestBed creates an
Angular dependency-injection and template environment. HTTP tests should use
Angular’s HTTP testing provider/controller so they assert method, URL, headers,
body, success, and error behavior without a real backend. Router tests need
router providers or a router testing setup. Browser-only APIs such as canvas and
animation frames need controlled fakes and teardown.

At the audit checkpoint, most tests only asserted creation. The suite failed for
an obsolete starter assertion, missing providers, a real form defect, animation
change detection, unmocked canvas behavior, and an escaped HTTP request. This is
valuable evidence that the test harness itself had to be stabilized before it
could protect the quiz workflow. The revision and Dashboard/Login phases added
contract, state, accessibility, navigation, and canvas-lifecycle tests. The
current complete suite passes 72 tests across 31 files without contacting a
backend.

Useful testing pyramid for Revisee:

1. Pure tests for mapping, timer calculations, answer-set preparation, and
   error interpretation.
2. Service HTTP contract tests with no network.
3. Component tests for forms, loading/error/empty states, answer secrecy, and
   navigation.
4. A small number of end-to-end tests for login → create/select → revise →
   submit → result once an E2E tool is deliberately selected.

## Existing design decisions worth explaining

- **Feature services:** API calls are grouped by domain rather than placed in
  page components. This is a good base, though DTOs need strengthening.
- **Nested authenticated layout:** shared navigation is composed once while
  child routes change.
- **Functional guard/interceptors:** modern Angular functions use `inject()` and
  avoid unnecessary classes.
- **Reference-counted loader:** unlike a boolean, a count handles concurrent
  requests without hiding the spinner when only one request finishes.
- **Backend ownership as authority:** client routing improves UX, but every
  sensitive lookup is scoped by the authenticated backend user.
- **No global store yet:** there is not enough demonstrated shared mutable state
  to justify one. Add complexity when product behavior requires it.

## Honest interview summary

“The current Revisee frontend is a standalone Angular application with nested
authenticated routing, feature-oriented API services, functional guards and
interceptors, RxJS HTTP flows, and signal-based UI services. Authentication,
basic learning-item management, Topics, dynamic PDF/question-bank views,
dashboard reads, and the complete revision-session lifecycle are represented. Revision DTOs separate answer-safe
questions from completed results, while grading remains server-side. Weak-area
UI, a dedicated paged learning library, and build-budget debt remain honest
next steps. The Home dashboard itself now shows
only real supported data.”
