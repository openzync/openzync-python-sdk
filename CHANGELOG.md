# Changelog

All notable changes to this project will be documented in this file.

<!-- towncrier release notes start -->

## [1.0.0] - 2026-10-22

### Breaking Changes

- **BREAKING:** dead public surface removed — 7 model exports that were never part of any client response/request flow (`IngestMemoryRequest`, `FactBatchRequest`, `PaginatedGraphNodes`, `PaginatedGraphEdges`, `UserCreateRequest`, `UserUpdateRequest`, `SessionCreateRequest`) are gone from `openzync.models`, and the unused `request_stream` helper was removed. `openzync._version.__version__` no longer falls back to a fake `"0.0.0"`: importing from an unpackaged tree now raises `RuntimeError` — reinstall the package (`pip install openzync`) instead of importing from source. (+dead-exports-removed)
- Default `max_messages` to 500 and clamp any larger value to the backend's `le=500` limit — callers relying on the previous 1000 default now receive 500 messages. (+langchain-max-messages-cap)
- **BREAKING:** removed the dead `project_id` constructor params and tool input fields across the LangChain integration (`OZMemory`, `OZChatMessageHistory`, `OZGraphRetriever`, `GraphSearchInput`, `GraphNodeDetailInput`, `ListGraphNodesInput`, `AddFactsInput` and the corresponding `_run`/`_arun` signatures). The value was accepted but never sent — the transport resolves the project from the API key — and it appeared as a required LLM tool parameter. `OZGraphRetriever` document metadata no longer includes a `project_id` key (the echoed caller-supplied value was misleading, not the real project). Pass `session_id`/`client` only; drop `project_id` from all LangChain call sites. (+langchain-remove-project-id)
- **BREAKING:** response models overhauled to match core's real contracts — `ProjectMemberResponse.project_id` was removed (core never returns it; the project is resolved from the API key) and `ProjectMemberResponse.created_at` is now a `datetime` instead of a `str`. Eight response models across the facts, memory, observation, schema, session, user, project and graph domains gained previously-missing required fields (e.g. `organization_id`, `project_id`, `superseded_count`, `pending_enrichment_count`) and typed `datetime` timestamps, so constructing them from partial/legacy dicts now raises `pydantic.ValidationError`. Parse API responses through the models rather than hand-building them. (+models-overhaul)
- BREAKING: per-call transport — the shared `_async` client is gone and `_SyncDomainWrapper(owner, domain)` takes ownership of its domain client. Also: automatic Idempotency-Key generation on mutating calls (one key per logical call, reused across retries; pass your own to dedupe across calls) and optional `total` on list models. (+per-call-transport-idempotency)
- **BREAKING:** `AsyncProjectsClient.list()` now returns core's real contract — a flat `list[ProjectResponse]` — instead of the fabricated `{"data", "next_cursor", "has_more"}` envelope; the `cursor` param is gone (core paginates offset-based, so advance `offset` explicitly) and `sort_by`/`sort_dir` were added. `list_iter()` now offset-paginates and yields typed `ProjectResponse` models (the old envelope always carried `has_more=False`, so iteration silently stopped after page one). `list_members()` returns a flat `list[ProjectMemberResponse]` instead of the envelope dict; `limit`/`cursor` are gone (core's members endpoint is unpaginated and ignored them) in favour of `sort_by`/`sort_dir`. (+projects-list-typed)
- **BREAKING:** `AsyncProjectsClient.update_member()` now requires an explicit `role` — it used to default to `"member"`, so a caller that meant to change nothing silently demoted a project owner to member (core requires the query parameter too). Pass the intended role (`"owner"` or `"member"`) on every call. (+projects-update-member-role-required)
- **BREAKING:** `SyncPaginatedIterator` was deleted — `AsyncPaginatedIterator` is now dual-mode and drives both sync (`for page in iter(client.list_iter(...))`) and async (`async for page in await client.list_iter(...)`) iteration, so the separate sync class is redundant. Import `AsyncPaginatedIterator` from `openzync._pagination` (or use the client `*_iter()` methods) instead. (+sync-iterator-removed)
- Raise a clear SDK error directing callers to `AsyncOpenZync` when sync wrappers are invoked inside a running event loop, instead of the opaque `asyncio.run()` `RuntimeError`. (+sync-loop-guard)
- Return `SessionListResponse` and `UserListResponse` models from `sessions.list()` and `users.list()` instead of bare dicts — access fields as attributes. (+typed-list-responses)
- **BREAKING:** `AsyncUsersClient.create()` no longer accepts `permissions`, and the `permissions` field was removed from `UserCreateRequest` — core validates but silently drops it on `POST /v1/users` (permissions are seeded server-side from the role defaults), so passing it granted nothing. Use `update()` after creation to set permissions. (+users-create-no-permissions)
- **BREAKING:** client-side guards that raised `ValueError` now raise typed errors inside the `OpenZyncError` taxonomy, so `except ValueError` no longer catches them — catch `OpenZyncError` (or the specific subclass) instead. `AsyncHTTPTransport.resolve_project_id()` raises `AuthorizationError` when the API key has no project scope; empty `name`/`sample_text`, an unknown `schema_type`, and ambiguous `subject_id`/`subject_ids` raise `ValidationError`. (+valueerror-to-typed)
- Map HTTP 405 and 500 to dedicated SDK errors and restrict `GraphTimeoutError` to graph timeouts (other 504s map to `ServiceUnavailableError`); RFC7807 `title`/`type` no longer leak into `detail`. (+error-map-405-500)
- **BREAKING:** `AsyncMemoryClient.delete()` now requires keyword-only `confirm` (must equal the project ID) sent as the DELETE body; `OZChatMessageHistory.clear()/aclear()` without `confirm` only clear the local cache with a `DeprecationWarning` — pass `confirm` for the server wipe. `delete_memory` MCP tool requires `confirm`. Transport: `204`/empty-2xx on body-expecting methods and non-JSON 2xx now raise `OpenZyncError` (no more `None`/`{"_raw": ...}` fallbacks; `None` is returned only for `DELETE` + `204`); `POST` retries only with an `Idempotency-Key` header, otherwise fails fast; sync clients raise `OpenZyncError` (not `RuntimeError`) inside a running loop. `AsyncFactsClient.add()` accepts an optional `idempotency_key` enabling safe retry. (+p0-sdk-http-confirm)
### Fixed

- Translate the `cursor` argument of `facts.list()` to `offset` (backend cursors are offset-encoded strings); garbage cursors raise SDK `ValidationError`. (+facts-cursor-offset-translation)
- Filter LangChain retriever results on the `rrf_score` ranking signal (falling back to `score`) and drop the never-sent `project_id` from result metadata. (+retriever-rrf-score)
- Map every transport-level failure onto the SDK error taxonomy: `httpx.TransportError` (connection refused, DNS failure, protocol error, pool timeout) now raises `openzync._errors.TransportError` instead of escaping as a raw `httpx` exception, and a timeout raises the new `RequestTimeoutError` (a `TransportError` subclass). `TransportError` means "the API never answered"; `ExternalServiceError` still means "the API answered 502". (+transport-error-taxonomy)
### Changed

- Always send a reason body on fact retraction, defaulting to `"retracted via SDK"` when none is given. (+facts-retract-default-reason)
### Internal

- Add `scripts/export_openapi.py` to snapshot the core OpenAPI schema for SDK contract checks, plus a regeneration note. (+openapi-export-script)
- Add a pytest coverage gate at 95 (ratchet: raise toward 100 as coverage improves). (+coverage-gate-95)
## [Unreleased]

## [1.0.0b5] - 2026-08-28

### BREAKING
- **BREAKING:** API key `scopes` field renamed to `permissions` (same
  permission vocabulary as users). Key defaults changed from `['read','write']`
  to `['project:read','project:write']`.
- **BREAKING:** `AsyncUsersClient.create` and `AsyncUsersClient.update` now
  accept an optional `permissions` argument, and `UserResponse` now carries the
  user's effective `permissions` list (empty array = full access / admin).
  Omitting `permissions` on create/update leaves the backend defaults in place.
- **BREAKING:** `AsyncUsersClient.create`, `AsyncUsersClient.update`, and
  `AsyncUsersClient.delete` now require an **org-admin credential** (a JWT
  dashboard session for a user with the `admin` role).  Project-scoped API
  keys — and any non-admin credential — receive `401 Unauthorized` on these
  endpoints.  Read-only user endpoints (`list`, `get`) are unaffected.

### Added
- Classifications, observations, search, and structured extractions clients.

## [0.4.0] - 2026-07-04
### Changed
- **Changed:** Renamed API class `OpenZync` to `OpenZync`, `AsyncOpenZync` to `AsyncOpenZync`, `OpenZyncError` to `OpenZyncError` for consistency with the renamed product.

## [0.3.0] - 2026-06-23

### Added
- First PyPI release as `openzync`.
- Migrated to `src` layout (PEP 517) with Hatchling build backend.
- Dynamic versioning via Git tags (`hatch-vcs`).
- `py.typed` marker for PEP 561 type hint support.
- CHANGELOG.md, `.gitignore`.
- GitHub Actions CI/CD for publishing to PyPI and TestPyPI (trusted publishing).

### Changed
- Moved package from flat layout to `src/openzync/`.
- Upgraded build system from setuptools to Hatchling.
- Version now derived from Git tags (via `hatch-vcs`), no longer hardcoded.
- Updated `User-Agent` header to use runtime version detection.
- Classifier updated to "Development Status :: 4 - Beta".
- Dependency bounds relaxed to minimum-version ranges.

### Fixed
- User-Agent version string now tracks package version automatically.
