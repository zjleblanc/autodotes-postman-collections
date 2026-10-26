# TMDB API Collection

Postman v3 collection for The Movie Database (TMDB) API v3, generated from the
OpenAPI specification and organized by API resource.

Collection base URL defaults to:

- `https://api.themoviedb.org`

## Auth

The collection uses bearer authentication:

- `Authorization: Bearer {{tmdb_bearer_token}}`

To use the collection, create a TMDB account and generate a v3 Read Access
Token in your TMDB API settings:

- [https://www.themoviedb.org/settings/api](https://www.themoviedb.org/settings/api)

## Required Variables

- `base_url` (default: `https://api.themoviedb.org`)
- `tmdb_bearer_token` (required for authenticated calls)
- `tmdb_api_key` (optional, included for custom key-based requests)

## Folder Catalog

The collection contains 152 requests across TMDB resources.

| Folder | Requests | Notes |
| --- | ---: | --- |
| `account-{account_id}` | 11 | Account details, favorites, rated, watchlist |
| `authentication` | 7 | Token/session creation and validation flows |
| `certification` | 2 | Movie and TV certification endpoints |
| `collection-{collection_id}` | 3 | Collection details and related media |
| `company-{company_id}` | 3 | Company details and associated titles |
| `configuration` | 6 | API configuration, countries, jobs, languages |
| `discover` | 2 | Movie and TV discovery/search by filters |
| `genre` | 2 | Genre list endpoints |
| `guest_session-{guest_session_id}-rated` | 3 | Guest session rating endpoints |
| `keyword-{keyword_id}` | 2 | Keyword details and related titles |
| `list` | 7 | List management and item operations |
| `movie` | 24 | Movie details, alternatives, credits, media, states |
| `network-{network_id}` | 3 | Network details and related content |
| `person` | 12 | Person details, credits, images, translations |
| `search` | 7 | Multi, movie, TV, person, and keyword search |
| `trending` | 4 | Trending endpoints by media type/window |
| `tv` | 48 | TV series, season, and episode operations |
| `watch-providers` | 3 | Available watch providers metadata |

Root-level requests:

- `Details`
- `Details-1`
- `Find By ID`

## Usage Notes

- Most endpoints require auth; set `tmdb_bearer_token` before sending requests.
- Path variables (for example `account_id`, `movie_id`, `series_id`) must be
  set per request context before execution.
