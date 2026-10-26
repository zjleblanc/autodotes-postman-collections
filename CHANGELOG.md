# Changelog

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
