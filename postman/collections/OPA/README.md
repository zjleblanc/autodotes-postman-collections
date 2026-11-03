# OPA Collection

Postman v3 collection for the Open Policy Agent REST API, authored from the
authoritative reference:

- [https://www.openpolicyagent.org/docs/rest-api](https://www.openpolicyagent.org/docs/rest-api)

Collection base URL defaults to:

- `http://localhost:8181`

## Auth

Bearer authentication is optional and only required when OPA is started with
`--authentication=token`:

- `Authorization: Bearer {{opa_token}}`

Leave `opa_token` empty for a default local `opa run --server` instance.

## Required Variables

- `base_url` (default: `http://localhost:8181`)
- `opa_token` (optional; required only with token authentication)
- `policy_id` (default: `example1`)
- `document_path` (default: `opa/examples/public_servers`)
- `filter_path` (default: `filters/include`)

## Folder Catalog

The collection contains 20 requests across the REST API groups.

| Folder | Requests | Notes |
| --- | ---: | --- |
| `Policy` | 4 | List, get, create/update, delete policy modules |
| `Data` | 6 | Get, evaluate with input, webhook (`/v0`), put, patch, delete |
| `Query` | 3 | Default decision (`POST /`), ad hoc GET and POST |
| `Compile` | 2 | Partial evaluation and data-filter compilation |
| `Health` | 3 | Built-in `/health`, policy-based live and ready |
| `Config` | 1 | Active configuration (secrets omitted) |
| `Status` | 1 | Labels, bundles, plugins |

## Usage Notes

- Start a local server with `opa run --server` (listens on port 8181 by
  default).
- Bundles are the preferred way to update policies in production. Bundle-owned
  package paths cannot be overwritten through the Policy API.
- Undefined documents on Data API GET/POST return **200** without a `result`
  property. The webhook API (`/v0/data/...`) returns **404** for missing
  documents.
- `/health/live` and `/health/ready` require Rego under package
  `system.health` and return 500 until those rules evaluate to true.
- Cross-cutting query parameters (`pretty`, `metrics`, `explain`,
  `provenance`, and related flags) are present but disabled on the operations
  that support them. Enable them as needed for debugging.
