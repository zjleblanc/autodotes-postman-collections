# Proxmox Collection

Postman v3 collection for the Proxmox VE REST API, generated from the official
API Viewer schema.

Collection base URL defaults to:

- `https://localhost:8006/api2/json`

## Auth

This collection uses cookie-based auth at the collection level:

- Header `Cookie: PVEAuthCookie={{pve_ticket}}`

For non-GET requests, the collection pre-request script injects:

- `CSRFPreventionToken: {{csrf_token}}`

### Recommended login flow

1. Set `base_url` to your Proxmox endpoint.
2. Run `Access > Create Ticket` (configured with `auth: noauth`).
3. Its response script stores:
   - `pve_ticket`
   - `csrf_token`
4. Run other requests; auth and CSRF are applied automatically.

### Alternative auth model

For long-lived automation, you can replace collection auth with an API token
header (`Authorization: PVEAPIToken=...`) in your own fork/workspace.

## Required Variables

- `base_url` (default: `https://localhost:8006/api2/json`)
- `pve_ticket` (auto-managed by `Access > Create Ticket`)
- `csrf_token` (auto-managed by `Access > Create Ticket`)

## Folder Catalog

The collection contains 680 requests.

| Folder | Requests | Notes |
| --- | ---: | --- |
| `Access` | 45 | Authn/authz administration including `Domains` (6), `Groups` (5), `Openid` (3), `Roles` (5), `TFA` (6), `Users` (12) |
| `Cluster` | 262 | Cluster-wide operations including `ACME` (15), `Backup` (6), `Ceph` (10), `Firewall` (31), `HA` (23), `Notifications` (31), `SDN` (78), and others |
| `Nodes` | 360 | Node-scoped operations including `Ceph` (43), `Disks` (18), `LXC` (62), `QEMU` (97), `Storage` (20), and operational endpoints |
| `Pools` | 7 | Pool CRUD and listing |
| `Storage` | 5 | Storage listing and management |

Root-level requests:

- `Version` (1 request)

## Usage Notes

- If requests fail with `401`/`403`, create a fresh ticket and rerun.
- If write requests fail with CSRF-related errors, refresh ticket/CSRF tokens
  via `Access > Create Ticket` and retry.
