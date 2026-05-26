# AnyFast Contracts

The `contracts` directory is the shared contract and collaboration layer for the AnyFast full-stack project.

It coordinates work between:

- Frontend project: `G:\anyfast\reasearch-front`
- Frontend local URL: `http://localhost:5173`
- Backend project: `G:\anyfast\research-agent`
- Backend local URL: `http://localhost:8000`

## Source Of Truth

`openapi.yaml` is the only source of truth for API contracts.

Agents must not infer request fields, response fields, status codes, or error formats from frontend mocks or backend implementation details. If the API contract is missing or unclear, create a GitHub Issue and record the request in `api-requests.md`.

GitHub Issue is the only task communication source. Markdown files in this directory support collaboration, but task ownership, status, and cross-agent handoff must be tracked through GitHub Issues.

## Directory Files

| File | Purpose |
| --- | --- |
| `openapi.yaml` | Canonical OpenAPI 3.0.3 contract for all frontend-backend API integration. |
| `api-requests.md` | Frontend Agent request queue for missing or unclear backend APIs. |
| `integration-log.md` | Integration issue log for local integration, contract mismatches, and E2E failures. |
| `decisions.md` | Architecture and contract decision log for durable AI Agent collaboration. |
| `README.md` | Collaboration rules, workflow, and task communication standards. |

## Collaboration Rules

- OpenAPI is the only interface contract source.
- GitHub Issue is the only task communication source.
- Do not guess fields.
- Do not invent undocumented API behavior.
- Do not skip tests.
- Do not merge frontend integration against mock-only assumptions.
- Do not implement backend endpoints without updating `openapi.yaml`.
- Every contract change must be reviewable through OpenAPI diff and related tests.

## Frontend Agent Workflow

1. Scan existing mocks, pages, components, and data dependencies.
2. Compare required API behavior against `openapi.yaml`.
3. If an API is missing or unclear, create a GitHub Issue using the standard API request format.
4. Add the request to `api-requests.md`.
5. Wait for the Backend Agent to update `openapi.yaml`.
6. Integrate the real API from `http://localhost:8000`.
7. Remove or isolate obsolete mock assumptions.
8. Run frontend tests and relevant integration checks.
9. Update the GitHub Issue and `integration-log.md` with verification results.

## Backend Agent Workflow

1. Process API requests from GitHub Issues.
2. Review the related entry in `api-requests.md`.
3. Update `openapi.yaml` before or alongside implementation.
4. Implement the backend endpoint in `G:\anyfast\research-agent`.
5. Add request validation, response shaping, and error handling that match OpenAPI.
6. Write backend tests for the endpoint.
7. Run backend tests.
8. Mark the request as implemented in `api-requests.md`.
9. Update the GitHub Issue with implementation notes and test evidence.

## Integration Workflow

1. Start backend at `http://localhost:8000`.
2. Start frontend at `http://localhost:5173`.
3. Run E2E and integration tests against real APIs.
4. Record contract mismatches, runtime errors, and data-shape issues in `integration-log.md`.
5. Fix either frontend integration or backend implementation according to `openapi.yaml`.
6. If OpenAPI is wrong, update the contract first, then update implementation and tests.
7. Re-run E2E tests until the integration issue is verified.

## GitHub Issue Template

Use this format when requesting a missing or unclear API.

```markdown
Title: API Request: xxx

## Page

<Page name or route>

## Component

<Component name and file path if known>

## Endpoint

<Proposed endpoint path>

## Method

<GET | POST | PUT | PATCH | DELETE>

## Params

<Path params, query params, headers, or request body fields>

## Response

<Required response fields and example shape>

## Acceptance

- OpenAPI is updated.
- Backend endpoint is implemented.
- Backend tests cover success and failure cases.
- Frontend integrates the real API without guessing fields.
- Frontend or E2E tests verify the user flow.
```

## Contract Change Standard

Every API contract change must include:

- Path and method.
- Tag.
- Request params or request body schema.
- Response schema.
- Error responses where applicable.
- Stable field names and types.
- Tests in the owning project.

## Agent Ownership

Frontend Agent owns page/component integration, mock replacement, and frontend tests.

Backend Agent owns OpenAPI updates, backend endpoint behavior, validation, persistence, and backend tests.

Integration ownership is shared. The contract in `openapi.yaml` decides expected behavior when frontend and backend disagree.
