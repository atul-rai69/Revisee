# Backend-to-frontend feature map

Audit date: 2026-09-05

The backend calls the grouping concept a **label** in code and API contracts.
The product-facing term in this documentation is **Topic**. The revision flow
uses that term while retaining backend `label_*` names at the API boundary.

Status meanings:

- **Implemented**: a reachable frontend flow calls the current backend contract.
- **Partial**: some UI/call exists, but behavior or contract is incomplete.
- **Missing**: backend capability exists with no frontend implementation.
- **Unknown/internal**: backend persistence exists but no public endpoint exists
  for a frontend client.

## Endpoint map

| Backend endpoint | Backend capability | Frontend status | Evidence and mismatch |
|---|---|---|---|
| `POST /register` | Creates account/session and returns a token | Missing | No registration UI or misleading inert link is shown. Backend currently accepts username, email, and password as query parameters. |
| `POST /login` | Authenticates and returns bearer token | Implemented | Typed `AuthService.login()` and the reactive Login form preserve `{username, password}` and `access_token`. |
| `POST /logout` | Invalidates current authenticated session | Implemented | Sidebar calls it and clears token on success. Failure retains the local token. |
| `GET /labels` | Lists owned Topics | Implemented | `LabelService.getLabels()` feeds Topics and item creation. UI calls them Labels. |
| `POST /labels` | Creates an owned Topic | Implemented | Topic form sends `{label_name}` and refreshes the list. |
| `PATCH /labels` | Renames an owned Topic | Implemented | Topic edit mode sends `{id, label_name}`. |
| `POST /learning-items` | Creates item, labels, media, and generated revision content | Partial | Multipart names match: `title`, `description_text`, JSON `labels`, repeated `images`, repeated `pdfs`. The legacy search control is now isolated from its reactive parent, but the UI still claims upload limits it does not enforce. |
| `DELETE /learning-items` | Deletes an owned item | Implemented | Dashboard sends body `{id}`, prevents duplicate deletion, and isolates the delete action. |
| `GET /learning-item/{item_id}` | Returns owned item, media URLs, theory, key points, and question-bank view | Implemented | Nullable fields are typed accurately; detail renders real counts/media, approved Cloudinary HTTPS PDF previews, honest empty states, and a complete question-bank route. |
| `GET /dashboard/summary` | Username and aggregate counts | Implemented | Dashboard binds username, total items, total Topics, and login-date count. |
| `GET /dashboard/learning-items-summary` | Owned item-card summaries | Implemented | Dashboard maps only returned fields, searches loaded items, and provides loading/empty/error/retry states. Pagination remains unavailable. |
| `POST /generate` | Authenticated regeneration for an owned item | Implemented | Detail/question-bank actions send `{learning_item_id,title,description}`, prevent duplicate clicks, consume `{message}`, and reload canonical item data. |
| `POST /revision-sessions` | Creates stored-question RANDOM, LABEL, or SMART session | Implemented | Setup maps Quick/Topic/Smart controls to exact requests and handles validation and shortage errors. It sends `allow_ai_generation: false`; shortage generation is not promised. |
| `GET /revision-sessions/{session_id}` | Resumes identical ordered answer-safe snapshots | Implemented | Guarded runner reloads persisted order and redirects a completed session to results. |
| `POST /revision-sessions/{session_id}/submit` | Grades full answer set and updates attempts/statistics/mastery | Implemented | Runner sends one option and bounded measured time per `session_question_id`, blocks duplicates, and never grades locally. |
| `GET /revision-sessions/{session_id}/result` | Returns stable completed result with answers/explanations | Implemented | Result route reloads the canonical DTO and shows answer review, explanation, timing, and mastery delta. |
| `GET /weak-areas` | Paginates owned weak/due/insufficient-evidence items or Topics | Missing | No service, filter, or page. |

The generated OpenAPI document contains 14 paths and 17 HTTP operations. No
`/api/v1` prefix exists.

## Capability map beyond endpoints

| Capability | Backend state | Frontend state |
|---|---|---|
| Authentication/session ownership | Implemented and required on protected endpoints | Token guard/interceptor implemented; no registration; client token handling has limitations. |
| Secure password storage and legacy transition | Backend concern, implemented | No special UI beyond login. |
| Topics | List/create/update and ownership implemented | CRUD is partial: list/create/update work; search/sort/pagination/delete do not. Backend has no delete route. |
| Learning items | Create/detail/delete, Topic ownership, media, revision content | API calls are wired; detail and full question bank use real data; no edit/list page distinct from dashboard. |
| Media storage | Images/PDFs accepted and stored; URLs returned | Upload works through creation; item detail renders image gallery and embedded/openable PDF resources. |
| Full learning-item AI generation | Used by create and `/generate` | Creation triggers it indirectly; manual authenticated regeneration is wired and refreshes the item. |
| Controlled question-only generation | Internal provider-neutral foundation and persistence | Unknown/internal: no public frontend endpoint. |
| RANDOM session | Public create/resume/submit/result lifecycle | Implemented as Quick revision. |
| LABEL session | Public strict per-label quota lifecycle | Implemented as Topic revision. |
| SMART session | Public personalized selection with RANDOM fallback | Implemented, including honest fallback messaging. |
| Answer-safe snapshots | Backend create/resume omit answers | Implemented with a separate pre-submit DTO that has no answer-bearing fields. |
| Attempts and grading | Snapshot-based, atomic on complete submission | Implemented as one complete submission; grading stays server-side. |
| Mastery | Item/Topic mastery updated during submission | Partial presentation: result deltas are shown; no aggregate endpoint is invented. |
| Question statistics | Persisted internally during submission | Unknown/internal: no public endpoint. |
| Weak areas | Public item/Topic classification endpoint | Missing. |
| Dashboard/Home | Basic counts, Topics, and item summaries | Implemented for available contracts. Unsupported review, progress, recently viewed, analytics, and session data is absent. |

## Confirmed contract/type mismatches

1. Manual generation is full revision-content regeneration, not a dedicated
   question-only endpoint; it can replace theory and append key points as well
   as questions.
2. PDF inline rendering remains dependent on browser/provider response headers;
   the explicit Open PDF action is the fallback.
3. The obsolete `Login` service calls `/auth/login`, which does not exist.

## Verified backend limitations relevant to the roadmap

- There is no backend Topic-delete or learning-item-edit endpoint.
- There is no public question-statistics or general mastery-summary endpoint.
- Session creation uses stored questions only; AI shortage generation is not a
  public session behavior at this checkpoint.
- Registration’s query-parameter contract should be treated carefully because
  URLs may be logged by infrastructure.
