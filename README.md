# autodotes-postman-collections

Postman v3 Git-synced workspace assets for multiple APIs used in homelab and
platform automation.

This repository currently contains four collections:

- `AAP` (Ansible Automation Platform)
- `Proxmox` (Proxmox VE REST API)
- `AO` (Syntara Orchestration API)
- `TMDB API` (The Movie Database API v3)

## Collections

| Collection | Requests | Auth model | Docs |
| --- | ---: | --- | --- |
| AAP | 1,281 | Bearer token (`{{aap_token}}`) | [`postman/collections/AAP/README.md`](postman/collections/AAP/README.md) |
| Proxmox | 680 | Cookie header (`PVEAuthCookie={{pve_ticket}}`) + CSRF token on writes | [`postman/collections/Proxmox/README.md`](postman/collections/Proxmox/README.md) |
| AO | 189 | Bearer token (`{{ao_access_token}}`) with auto-login script | [`postman/collections/AO/README.md`](postman/collections/AO/README.md) |
| TMDB API | 152 | Bearer token (`{{tmdb_bearer_token}}`) | [`postman/collections/TMDB API/README.md`](postman/collections/TMDB%20API/README.md) |

## Use These Collections In Your Workspace

Choose one of the approaches below to incorporate one or more collections.

### Option 1: Fork from Postman workspace (recommended for collaboration)

1. Open the source workspace in Postman.
2. Open the collection you want to reuse (for example `AAP` or `Proxmox`).
3. Select **Fork** and choose your destination workspace.
4. Configure variables in your destination environment.

Use this when you want to receive updates and open pull requests back to the
source collection.

### Option 2: Import from this Git repository

1. Clone this repository locally.
2. In Postman, select **Import**.
3. Import the specific collection folder under `postman/collections/<name>/`.
4. Create or select an environment and set the required variables.

Use this when you only need one-time copy/import of one or more collections.

### Option 3: Connect your own Postman workspace to this repo (Git sync)

1. Create or select your destination Postman workspace.
2. Connect that workspace to a Git repository.
3. Copy the desired collection directories from this repo into your synced
   `postman/collections/` path.
4. Pull/push through your normal Git workflow.

Use this when your team wants Git-native review and version control for
collection changes.

## Required Variables by Collection

Set these in your Postman environment (or collection variables where noted):

### AAP

- `aap_base_url` (default in collection: `https://ansible.autodotes.com`)
- `aap_token` (secret bearer token)

### Proxmox

- `base_url` (default in collection: `https://localhost:8006/api2/json`)
- `pve_ticket` (auto-managed by `Access > Create Ticket`)
- `csrf_token` (auto-managed by `Access > Create Ticket`)

### AO

- `base_url` (default in collection: `http://localhost:8000`)
- `ao_username` (for auto-login)
- `ao_password` (for auto-login)
- `ao_access_token` / `ao_access_token_expiry` are managed by the collection
  pre-request script and should not be manually set.

### TMDB API

- `base_url` (default in collection: `https://api.themoviedb.org`)
- `tmdb_bearer_token` (TMDB v3 Read Access Token)
- Optional: `tmdb_api_key` if you need key-based flows in custom requests.

## Repository Layout

- `postman/collections/` - collection sources (one folder per collection)
- `postman/environments/` - environment files
- `postman/globals/` - workspace globals
- `postman/documents/` - workspace documents
- `postman/skills/` - local API workflow skills for this repository
- `.postman/resources.yaml` - local workspace binding metadata (gitignored)
