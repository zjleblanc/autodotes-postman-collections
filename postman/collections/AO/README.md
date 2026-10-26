# AO Collection

Postman v3 collection for the Syntara Orchestration API (`AO`), organized by
backend domain areas (`/api/v1/...`).

## Auth

The collection defines bearer auth at the top level:

- `Authorization: Bearer {{ao_access_token}}`

Token lifecycle is handled automatically by the collection pre-request script
in `.resources/definition.yaml`:

- If `ao_access_token` is missing or expired, it calls `POST /api/v1/auth/login`
  using `ao_username` and `ao_password`.
- It stores token expiry in `ao_access_token_expiry` and refreshes before hard
  expiration.
- Auth-management requests are excluded from auto-login to avoid recursion:
  `/auth/login`, `/auth/token`, `/auth/refresh`, `/auth/oidc`.

## Required Variables

- `base_url` (default: `http://localhost:8000`)
- `ao_username` (secret)
- `ao_password` (secret)

Do not manually set `ao_access_token` or `ao_access_token_expiry`; those are
collection-managed runtime variables.

## Folder Catalog

The collection contains 189 requests across 18 top-level folders.

| Folder | Requests | Notes |
| --- | ---: | --- |
| `AAP Proxy` | 10 | Proxy requests to AAP resources |
| `Admin` | 4 | Administrative lifecycle and maintenance endpoints |
| `Approvals` | 6 | Approval workflows and decisions |
| `Auth` | 10 | Login, token, refresh, logout, OIDC, CSRF, WS ticket |
| `Credentials` | 8 | Credential CRUD and listing |
| `Executions` | 7 | Workflow execution operations |
| `Files` | 6 | File upload/download and file metadata operations |
| `Identity Providers` | 7 | Identity provider management |
| `Integrations` | 19 | `LLM Models` (4), `MCP Tools` (4), `Project Assignments` (3), plus direct routes |
| `Invocations` | 6 | Invocation operations and retrieval |
| `Projects` | 29 | `Credentials` (6), `Policies` (6), `Role Assignments` (3), `Roles` (6), plus direct routes |
| `Role Assignments` | 4 | Global role assignment endpoints |
| `Roles and Policies` | 17 | `Authorization Queries` (5), `Policies` (6), `Roles` (6) |
| `Service Accounts` | 7 | Service account creation and management |
| `Settings` | 5 | Platform/runtime settings |
| `Tools` | 3 | Tool registration and lookup endpoints |
| `Users` | 27 | User routes plus nested `Groups` (12) |
| `Workflows` | 14 | Workflow routes plus nested `Versions` (6) |

## Usage Notes

- Run any authenticated request first; if credentials are set, the pre-request
  script obtains and caches a token automatically.
- If `ao_username`/`ao_password` are unset, auth-capable requests run without a
  token and usually return `401`/`403` until credentials are configured.
