# Changelog

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
