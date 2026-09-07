# Revisee frontend roadmap

This is a recommendation, not a statement of implemented behavior. It exposes
the backend’s current capabilities in small, reviewable increments and puts the
learning/revision loop ahead of analytics.

## Product navigation direction

Recommended primary navigation:

1. Home
2. My Learning
3. Revise
4. Weak Areas

Create Learning Item and Create Topic should be contextual actions within My
Learning, selectors, and empty states—not permanent primary navigation items.
Analytics should be added only when its data and screens are real. Settings
should not point to an experiment.

## Phase 1 — Reliable revision vertical slice (implemented 2026-09-06)

Objective: let a learner start, resume, complete, and understand one quiz using
the backend that already exists.

Delivered:

- Add strict DTOs for RANDOM/LABEL/SMART requests, answer-safe session
  questions, shortage errors, submission, completed results, and API errors.
- Add a `RevisionSessionService` for create, resume, submit, and result calls.
- Add a Revise setup page:
  - RANDOM: question count.
  - Topic quiz (backend LABEL): owned Topic selection and questions per Topic.
  - SMART: question count and clear explanation of possible RANDOM fallback.
- Add a quiz runner route, such as `/app/revision-sessions/:id`, keyed by
  `session_question_id`, preserving backend order and timing each answer.
- Resume IN_PROGRESS sessions from the server rather than generating local
  question order.
- Require one selected option for every question before full submission.
- Add a result route that shows score, timing, correct answers, explanations,
  and per-question mastery delta from the completed-result DTO.
- Handle 409 insufficient bank, already-completed/not-completed cases, exact
  answer-set 422, concealed 404, authentication expiry, loading, retry, and
  empty states.
- Preserve separate pre-submit and completed-result types so correct answers
  cannot accidentally enter the quiz UI.
- Repair the existing test harness failures and add HttpClient/controller,
  router, form, answer-secrecy, timer, resume, and result tests.

Why first: this completes Revisee’s core promise—turn saved learning material
into an owned, resumable, graded revision experience. It also starts producing
the mastery evidence needed by later personalization.

Intentional deferrals: draft answers are not persisted or described as
auto-saved; weak areas still have no frontend route; AI does not fill bank
shortages; and the pre-existing application-wide bundle/old-component CSS
budget debt was not hidden by raising limits. All three new revision component
styles remain below the configured 8 kB component-style error limit.

## Phase 2 — Learning library and contextual creation

Objective: make the material feeding quizzes dependable and easy to manage.

- Introduce `/app/learning-items` as the real My Learning library with search,
  Topic filtering, deterministic sorting, empty/error/loading states, and item
  cards.
- Move New Item to a contextual button/modal/route from the library and empty
  state. Preserve its multipart contract.
- Rename visible Labels to Topics while mapping API `label_*` fields at the
  client boundary.
- Make Topic create/rename available in context during item creation and in a
  secondary management surface.
- Remove or explicitly defer Topic deletion because the backend has no route.
- Correct nullable DTOs and render safe fallbacks.
- **Completed 2026-09-06:** bind real image/PDF resources and question counts,
  add embedded/openable PDFs, and add a complete owned question-bank page.
- **Completed 2026-09-06:** resolve `/generate` against the real backend contract
  and refresh canonical item detail after its message-only response.
- Enforce client-side upload constraints as usability checks while retaining
  backend validation as authority.

## Phase 3 — Weak areas and personalized revision

Objective: explain what needs work and turn that explanation into action.

- Add `WeakAreaService` for `/weak-areas`.
- Add item/Topic tabs and explicit classification views for demonstrated
  weakness, due review, and insufficient evidence.
- Display mastery score only when present, attempt evidence, accuracy, review
  timing, reason text, pagination, loading, and empty states.
- Add “Revise weak areas” entry points that start SMART sessions.
- Clearly show `requested_strategy` versus `strategy_used`; a SMART→RANDOM
  fallback is valid behavior, not an error.
- Do not infer statistical certainty beyond the backend’s attempt heuristic.

## Phase 4 — Dashboard consolidation (implemented 2026-09-06)

Objective achieved: remove prototype data and make Home an honest launch surface.

- Removed Items Reviewed, Topic Overview, Recently Viewed, remote sample imagery,
  and fake session content instead of replacing them with invented metrics.
- Bound real summary, Topic, and learning-item contracts with independent
  skeleton, empty, error, and retry states plus loaded-item search.
- Added contextual Add material, Quick revision, Choose Topics, Topic management,
  and item-open actions using routes that already exist.
- Omitted Continue Revision because no session-list contract or validated recent
  session mechanism exists.
- Redesigned login around the real auth contract with optional, lifecycle-safe
  canvas decoration and no unsupported account links.

## Phase 5 — Analytics and account experience

Objective: expose trends only after the core workflow is stable and the backend
offers suitable aggregates.

- Design analytics contracts for attempt history, score/mastery trends, and
  question statistics; do not build charts from unavailable data.
- Add registration after reviewing the backend query-parameter contract or
  coordinating a safer request-body migration.
- Decide logout-failure and token-storage policy.
- Add a real Settings route only when settings exist.
- Remove or isolate Playground, Canvas, and DesignPreview from production
  navigation/bundles.

## Shared components to introduce when first needed

- `PageState`: loading, error/retry, and empty presentation.
- `TopicPicker`: owned Topic search/multi-select with API-to-product naming.
- `LearningItemCard`: one real card used by dashboard/library.
- `QuizStrategyForm`: strict discriminated controls for RANDOM/LABEL/SMART.
- `QuestionCard`: answer-safe selection only.
- `QuizProgress` and `QuizTimer`: display/local timing without grading authority.
- `ResultQuestion`: completed answers/explanations only.
- `MasteryBadge` and `EvidenceBadge`: factual score/evidence presentation.
- Confirmation dialog for destructive actions.

Create abstractions only when two real consumers need them; do not build a
generic component framework in advance.

## Cross-cutting engineering work

- Keep one typed API contract area organized by feature.
- Scope bearer-token attachment to the configured backend origin.
- Prefer component-local signals for local UI state and RxJS for asynchronous
  HTTP flows; add a global store only if shared mutable state becomes complex.
- Cancel subscriptions/animation frames and revoke object URLs on destruction.
- Add route-level lazy loading as product sections grow.
- Remove external demo imagery and unnecessary runtime CDN dependencies.
- Reduce CSS duplication before raising build budgets; treat budgets as feedback,
  not an obstacle to silence.
- Add behavior tests around user workflows, not just construction tests.

## Exit criteria for Phase 1

- RANDOM, Topic/LABEL, and SMART requests are correctly constructed.
- A created session is answer-safe and renders in persisted order.
- Refresh/resume restores the same server session.
- Submission sends exactly one answer per `session_question_id`.
- Results are available only after completion and match backend order.
- Correct answers never appear in pre-submit models, fixtures, UI, or logs.
- All current and new frontend tests pass without real backend calls.
- Production build passes or has explicitly reviewed, justified budgets.
- Existing login, Topic, learning-item, and dashboard calls remain compatible.
