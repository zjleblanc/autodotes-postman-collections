# Changelog

## 2026-10-26 — Clear zleblanc-main environment variables

### Removed

- `postman/environments/zleblanc-main.environment.yaml`: cleared all 23 variables (AAP, Proxmox VE, Grafana, ServiceNow, Red Hat Console, Automation Hub, Dynatrace, Bitbucket, Slack, and demo webhook/OAuth placeholders) down to an empty `values: []`, to be re-populated as needed later.

## 2026-10-26 — Add AO collection generated from the Syntara domain model

### Added

- `postman/collections/AO/`: Postman v3 collection for the Syntara Orchestration API (FastAPI/SQLModel/Temporal), generated from the live domain model in `syntara-orchestration/syntara` (devel branch). 18 top-level folders mirror backend routers — Auth, Identity Providers, Users, Projects, Workflows, Executions, Invocations, Approvals, Credentials, Integrations, Tools, Files, Settings, Service Accounts, Role Assignments, Roles and Policies, Admin, and AAP Proxy — totaling 189 requests.
- Collection-scoped `http:beforeRequest` pre-request script that auto-authenticates via `Auth > Login` whenever `ao_access_token` is missing or expired, using the `ao_username`/`ao_password` collection variables, and caches the resulting token and expiry (`ao_access_token_expiry`) as collection variables for reuse across requests.
- `.postman/resources.yaml`: registered the new AO collection's workspace binding.

### Fixed

- `AAP Proxy/*`, `Auth/OIDC Authorize.request.yaml`, `Auth/OIDC Callback.request.yaml`, and 40+ other list/get requests: resolved `queryParams`-vs-URL mismatches, missing `formdata` `type` fields on two multipart requests, and a YAML nested-mapping parse error in `Executions/.resources/definition.yaml` — all surfaced and fixed via `postman collection lint`.

## 2026-10-26 — Add TMDB API collection from OpenAPI spec

### Added

- `postman/collections/TMDB API/`: Postman v3 collection generated from the TMDB OpenAPI spec (v3.1.0), containing 152 endpoints organized by resource.
- Collection-level Bearer authentication referencing `{{tmdb_bearer_token}}` and placeholder variables for `base_url`, `tmdb_bearer_token`, and `tmdb_api_key` in `.resources/definition.yaml`.

### Changed

- Flattened the collection structure by removing the redundant top-level `3` folder.
- Renamed generated `baseUrl` to `base_url` across all request files and examples for project consistency.

### Fixed

- `3/discover/Movie.request.yaml` and `3/discover/TV.request.yaml`: resolved query parameter mismatches found during collection linting.

## 2026-10-26 — Generate AAP collection from live API crawl

### Added

- `scripts/crawl_aap_api.py`: crawls the AAP gateway's six federated APIs (`gateway`, `controller`, `eda`, `galaxy`, `lightspeed`, `metrics`) using `AAP_POSTMAN_TOKEN_READONLY` and generates Postman v3 collection YAML. DRF APIs (gateway, controller, metrics) are crawled breadth-first via `OPTIONS` + `related`-link discovery; EDA and Galaxy are generated directly from their published OpenAPI specs.
- `postman/collections/AAP/`: single collection scoping Bearer auth (`{{aap_token}}`) and `{{aap_base_url}}` once at the top level, with one folder per API — Controller (557 requests), Galaxy (438), Gateway (141), EDA (121), Metrics (23), Lightspeed (1 placeholder; service not deployed on this instance).
- `postman/collections/AAP/README.md` documenting the crawl strategy, structure, and known limitations per API.

### Fixed

- `.postman/resources.yaml`: repaired the `AAP` collection's workspace binding after `postman workspace push` reported a false "Failed to create" on the large initial import — the import had actually succeeded server-side; the CLI's polling budget just timed out before confirming, leaving the binding unrecorded and risking a duplicate collection on retry.

## 2026-10-25 — Consolidate environments into zleblanc-main with standard variable naming

### Changed

- Merged Cansible, Demo, RHPDS, XOM, and The Movie DB API environments into a single `zleblanc-main` environment.
- Renamed variables to a consistent `<api>_<type>` convention (e.g. `aap_bearer_token` → `aap_token`, `snow_instance_pw` → `snow_password`, `bitbucket_app_pw` → `bitbucket_password`).
- Parametrized previously hardcoded ServiceNow (`zleblanc`) and Bitbucket (`zach-leblanc`) usernames as `snow_username` / `bitbucket_username`.
- Resolved `aap_base_url` collision (differed between Cansible/Demo and RHPDS) to a single canonical value: `https://ansible.autodotes.com`.
- Updated all `{{variable}}` references across Grafana, Slack, Proxmox VE, Dynatrace, ServiceNow, and Bitbucket collections to match renamed variables.
- Cleared a previously undetected live secret (`rhsm_offline_token`) in `postman/globals/workspace.globals.yaml` and fixed its invalid `description` field schema.

### Removed

- Dropped unused/orphaned variables: `accessTokenExpiry`, TMDB's leftover `value`/`key`/`in` keys, and the unreferenced `bitbucket_app_user` (conflicting with the actually-used username value).
- Deleted environment files: Cansible, Demo, RHPDS, XOM, The Movie DB API (both locally and in the Postman workspace).

## 2026-10-25 — Strip hardcoded secrets from all Postman files

### Changed

- Environments (Cansible, Demo, RHPDS): replaced all secret values with empty strings, preserving `type: secret` annotations.
- Collection definitions (AAP 2.4/2.5 Controller, EDA, Gateway): cleared inline bearer token variables.
- Request files (Dynatrace, Red Hat Downloads, AAP 2.4 Hosts, Support Services, Terraform Cloud): replaced hardcoded tokens with `{{variable}}` references.
- TMDB API documentation: redacted access tokens, request tokens, and passwords in request bodies and saved response examples.

### Added

- `.gitleaks.toml` allowlist for `.postman/resources.yaml` (contains Postman entity UUIDs, not secrets).
- `.postman/resources.yaml` added to `.gitignore` to keep workspace binding metadata local-only.

## 2026-10-25 — Add gitleaks pre-commit hook

### Added

- `.pre-commit-config.yaml` with gitleaks secret detection (v8.30.0).
- Pre-commit hook installed to scan for hardcoded secrets on every commit.

## 2026-10-25 — Initialize Postman collections repository

### Added

- Git repository initialized on `main` branch.
- Postman project scaffolded via `postman init` (CLI v1.75.0).
- `.postman/resources.yaml` workspace binding metadata.
- `postman/` directory tree: `collections/`, `environments/`, `specs/`, `flows/`, `globals/`, `sdks/`, and `skills/`.
- `AGENTS.md` with API task entry-point guidance.
- `.gitignore` for OS artifacts, editor temps, and `node_modules/`.
