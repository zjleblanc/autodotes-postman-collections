#!/usr/bin/env python3
"""
Crawl all federated top-level APIs behind the AAP gateway at
https://ansible.autodotes.com/api/ and generate Postman v3 collection YAML
under postman/collections/ -- one collection per top-level API: gateway,
controller, eda, galaxy, lightspeed, metrics.

Auth: Bearer token from env var AAP_POSTMAN_TOKEN_READONLY.

Discovery strategy per API
---------------------------
- gateway, controller, metrics: self-describing DRF REST APIs with no
  published machine-readable schema. Crawled breadth-first: start at the
  versioned API root (a flat dict of top-level resource URLs), then for
  each discovered endpoint call OPTIONS (to learn allowed HTTP methods and,
  for DRF, writable field schemas for POST/PUT/PATCH) and GET (to sample one
  item and follow its `related` links to discover sub-resource endpoints).
  Endpoints are deduplicated by a "templatized" path where numeric ID
  segments become `{id}`, which also prevents infinite loops on cross-links
  (e.g. every resource's `created_by` pointing back to `/users/{id}/`).

- eda: publishes a full OpenAPI 3 document at `/api/eda/v1/openapi.json`
  (paths relative to server `/api/eda/v1`). Collection generated directly
  from the spec.

- galaxy: exposes two overlapping OpenAPI documents --
  `/api/galaxy/v3/openapi.json` (curated, standard `{param}` placeholders)
  and the underlying Pulp app's `/api/galaxy/pulp/api/v3/docs/api.json`
  (broader, but most paths use Pulp's `{xxx_href}action/` dynamic-action
  convention that requires an already-fetched resource href rather than a
  fixed URL template). This script merges both specs' concrete
  `/api/galaxy/...`-prefixed paths and skips the `{xxx_href}`-style dynamic
  action paths, which aren't expressible as a fixed request URL.

- lightspeed: every probed path under `/api/lightspeed/` returned 404 on
  this AAP instance (service not deployed/enabled). A minimal placeholder
  collection documents that finding instead of a full crawl.

Usage:
    AAP_POSTMAN_TOKEN_READONLY=... python scripts/crawl_aap_api.py [api ...]

    With no arguments, crawls all six APIs. Optional positional args narrow
    to specific API keys (gateway, controller, eda, galaxy, lightspeed,
    metrics) for faster iteration.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import requests
import urllib3
import yaml

urllib3.disable_warnings()

# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
COLLECTIONS_DIR = ROOT / "postman" / "collections"
TOP_LEVEL_NAME = "AAP"
TOP_LEVEL_DIR = COLLECTIONS_DIR / TOP_LEVEL_NAME
REAL_BASE = "https://ansible.autodotes.com"
BASE_VAR = "{{aap_base_url}}"
TOKEN_VAR = "{{aap_token}}"

TIMEOUT = 25
MAX_ENDPOINTS_PER_API = 2500
MAX_SECONDS_PER_API = 20 * 60

ACTION_VERBS = {
    "cancel", "relaunch", "launch", "sync", "copy", "enable", "disable",
    "restart", "test", "preview", "notify", "cleanup", "import", "export",
    "revoke", "validate", "generate", "regenerate", "reset", "disassociate",
    "associate", "start", "stop", "activate", "deactivate", "add_role",
    "remove_role", "list_roles", "my_permissions", "set_label", "unset_label",
    "modify", "sign", "mark", "unmark", "repair", "replicate", "rebuild_metadata",
    "build_image", "curate", "versions", "profile_artifacts", "commit",
}

PARAM_RE = re.compile(r"\{([^}]+)\}")
HREF_PARAM_RE = re.compile(r"\{[a-zA-Z0-9_]*href[a-zA-Z0-9_]*\}")
INVALID_FS_CHARS = re.compile(r'[\\/:*?"<>|]')


def get_token() -> str:
    import os

    token = os.environ.get("AAP_POSTMAN_TOKEN_READONLY")
    if not token:
        sys.exit("ERROR: AAP_POSTMAN_TOKEN_READONLY is not set in the environment")
    return token


SESSION = requests.Session()
SESSION.headers.update({"Authorization": f"Bearer {get_token()}", "Accept": "application/json"})
SESSION.verify = False


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

def get_json(url: str):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  ! GET {url} failed: {e}", file=sys.stderr)
        return None, None
    if r.status_code >= 400:
        return None, r.status_code
    if "json" not in r.headers.get("content-type", ""):
        return None, r.status_code
    try:
        return r.json(), r.status_code
    except ValueError:
        return None, r.status_code


def get_options(url: str):
    try:
        r = SESSION.options(url, timeout=TIMEOUT)
    except requests.RequestException as e:
        print(f"  ! OPTIONS {url} failed: {e}", file=sys.stderr)
        return [], None
    allow = [m.strip() for m in r.headers.get("Allow", "").split(",") if m.strip()]
    body = None
    if "json" in r.headers.get("content-type", ""):
        try:
            body = r.json()
        except ValueError:
            body = None
    return allow, body


def discover_version_root(probe_path: str):
    """Resolve a top-level API probe path (e.g. /api/gateway/) to its
    current versioned root path (e.g. /api/gateway/v1/)."""
    data, _ = get_json(REAL_BASE + probe_path)
    if not isinstance(data, dict):
        return None
    cv = data.get("current_version")
    if isinstance(cv, str):
        return urlparse(cv).path if cv.startswith("http") else cv
    # metrics-style root: {"v1": "https://.../api/metrics/v1/"}
    for k, v in data.items():
        if isinstance(v, str) and re.match(r"^v\d+$", k):
            return urlparse(v).path if v.startswith("http") else v
    return None


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def templatize(path: str) -> str:
    return re.sub(r"/\d+(?=/|$)", "/{id}", path)


def singularize(word: str) -> str:
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith(("ses", "xes", "ches", "shes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss"):
        return word[:-1]
    return word


def titleize(word: str) -> str:
    return " ".join(p.capitalize() for p in re.split(r"[_\-]", word) if p)


def _truncate_with_hash(seg: str, max_len: int) -> str:
    if len(seg) <= max_len:
        return seg
    h = hashlib.sha1(seg.encode()).hexdigest()[:6]
    return seg[: max_len - len(h) - 1] + "-" + h


def sanitize_filename(name: str, max_len: int = 80) -> str:
    return _truncate_with_hash(INVALID_FS_CHARS.sub("-", name).strip(), max_len)


def sanitize_folder_segment(seg: str, max_len: int = 50) -> str:
    """Some AAP resources (e.g. DAB authenticator plugin configs) use long
    slug-style primary keys instead of numeric IDs, which can exceed
    filesystem-safe folder name lengths when sampled into a template."""
    seg = INVALID_FS_CHARS.sub("-", seg).strip() or "item"
    return _truncate_with_hash(seg, max_len)


# --------------------------------------------------------------------------
# YAML writing
# --------------------------------------------------------------------------

def _str_presenter(dumper, data):
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


yaml.add_representer(str, _str_presenter)


def dump_yaml(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, sort_keys=False, default_flow_style=False, allow_unicode=True, width=100000)


# --------------------------------------------------------------------------
# Endpoint model
# --------------------------------------------------------------------------

@dataclass
class EndpointInfo:
    path: str  # full absolute path with {param} placeholders
    methods: dict = field(default_factory=dict)  # method -> metadata (schema dict) or None
    engine: str = "drf"  # 'drf' | 'openapi'


# --------------------------------------------------------------------------
# DRF breadth-first crawler (gateway, controller, metrics)
# --------------------------------------------------------------------------

def crawl_drf(version_root_path: str, api_label: str) -> dict:
    """Breadth-first discovery of a DRF API's full surface, starting at its
    versioned root. Returns {template: EndpointInfo}."""
    endpoints: dict[str, EndpointInfo] = {}
    visited = set()
    queue: list[str] = []

    root_json, _ = get_json(REAL_BASE + version_root_path)
    if not isinstance(root_json, dict):
        print(f"  ! could not load root {version_root_path}", file=sys.stderr)
        return endpoints

    for rel in root_json.values():
        if not isinstance(rel, str):
            continue
        if rel.startswith("http"):
            rel = urlparse(rel).path
        if rel.startswith("/"):
            queue.append(rel)

    start = time.time()
    processed = 0
    while queue:
        if len(endpoints) >= MAX_ENDPOINTS_PER_API:
            print(f"  ! [{api_label}] hit MAX_ENDPOINTS_PER_API cap ({MAX_ENDPOINTS_PER_API}); stopping", file=sys.stderr)
            break
        if time.time() - start > MAX_SECONDS_PER_API:
            print(f"  ! [{api_label}] hit time budget ({MAX_SECONDS_PER_API}s); stopping", file=sys.stderr)
            break

        path = queue.pop(0)
        path = path.split("?")[0]
        template = templatize(path)
        if template in visited:
            continue
        visited.add(template)

        url = REAL_BASE + path
        allow, options_body = get_options(url)
        if not allow:
            continue

        methods = {}
        for m in allow:
            if m in ("HEAD", "OPTIONS"):
                continue
            field_schema = None
            if isinstance(options_body, dict):
                actions = options_body.get("actions", {})
                if isinstance(actions, dict):
                    field_schema = actions.get(m)
            methods[m] = field_schema

        endpoints[template] = EndpointInfo(path=templatize(path), methods=methods, engine="drf")
        processed += 1

        data = None
        if "GET" in methods:
            data, _ = get_json(url)

        def _norm(v):
            if not isinstance(v, str):
                return None
            if v.startswith("http"):
                v = urlparse(v).path
            return v if v.startswith("/") else None

        discovered = []
        if isinstance(data, dict):
            results = data.get("results")
            if isinstance(results, list) and results:
                item = results[0]
                if isinstance(item, dict):
                    u = _norm(item.get("url"))
                    if u:
                        discovered.append(u)
                    rel = item.get("related")
                    if isinstance(rel, dict):
                        discovered.extend(filter(None, (_norm(v) for v in rel.values())))
            rel = data.get("related")
            if isinstance(rel, dict):
                discovered.extend(filter(None, (_norm(v) for v in rel.values())))

        for d_path in discovered:
            d_path = d_path.split("?")[0]
            t = templatize(d_path)
            if t not in visited:
                queue.append(d_path)

        if processed % 50 == 0:
            print(f"  [{api_label}] processed={processed} queue={len(queue)} endpoints={len(endpoints)}")

    print(f"  [{api_label}] done: {len(endpoints)} unique endpoint templates")
    return endpoints


# --------------------------------------------------------------------------
# OpenAPI-driven collection (eda, galaxy)
# --------------------------------------------------------------------------

def load_openapi_endpoints_eda(spec_url: str, server_prefix: str) -> tuple[dict, dict]:
    spec, _ = get_json(REAL_BASE + spec_url)
    if not isinstance(spec, dict):
        return {}, {}
    components = spec.get("components", {})
    endpoints = {}
    for path, methods_obj in spec.get("paths", {}).items():
        if not isinstance(methods_obj, dict):
            continue
        full_path = server_prefix + path
        methods = {m.upper(): op for m, op in methods_obj.items() if m.upper() in
                   ("GET", "POST", "PUT", "PATCH", "DELETE")}
        if not methods:
            continue
        endpoints[full_path] = EndpointInfo(path=full_path, methods=methods, engine="openapi")
    return endpoints, components


def load_openapi_endpoints_galaxy(spec_urls: list) -> tuple[dict, dict]:
    endpoints = {}
    components = {"schemas": {}}
    for spec_url in spec_urls:
        spec, _ = get_json(REAL_BASE + spec_url)
        if not isinstance(spec, dict):
            print(f"  ! could not load {spec_url}", file=sys.stderr)
            continue
        components["schemas"].update(spec.get("components", {}).get("schemas", {}))
        for path, methods_obj in spec.get("paths", {}).items():
            if not isinstance(methods_obj, dict):
                continue
            if not path.startswith("/api/galaxy/"):
                continue  # stay scoped to the /api/galaxy/ top-level surface
            if HREF_PARAM_RE.search(path):
                continue  # Pulp dynamic {xxx_href}action/ paths need a fetched href, not a fixed URL
            methods = {m.upper(): op for m, op in methods_obj.items() if m.upper() in
                       ("GET", "POST", "PUT", "PATCH", "DELETE")}
            if not methods:
                continue
            if path not in endpoints:
                endpoints[path] = EndpointInfo(path=path, methods=methods, engine="openapi")
    return endpoints, components


# --------------------------------------------------------------------------
# Naming
# --------------------------------------------------------------------------

def build_display_name(raw_segs: list, folder_segs: list, method: str) -> str:
    ends_with_param = bool(raw_segs) and bool(PARAM_RE.match(raw_segs[-1]))
    if not folder_segs:
        folder_segs = ["root"]
    last = folder_segs[-1]
    is_action = last.lower() in ACTION_VERBS

    if len(folder_segs) == 1 and not is_action:
        if ends_with_param:
            verb = {"GET": "Get", "PUT": "Update", "PATCH": "Partial Update", "DELETE": "Delete"}.get(method, method.title())
            disp = titleize(singularize(last))
        else:
            verb = {"GET": "List", "POST": "Create"}.get(method, method.title())
            disp = titleize(last) if method == "GET" else titleize(singularize(last))
        return f"{verb} {disp}".strip()

    context = " ".join(titleize(singularize(s)) for s in folder_segs[:-1])
    child = titleize(last)
    if is_action:
        if method == "POST":
            name = f"{child} {context}".strip()
        elif method == "GET":
            name = f"Get {context} {child}".strip()
        else:
            verb = {"PUT": "Update", "PATCH": "Partial Update", "DELETE": "Delete"}.get(method, method.title())
            name = f"{verb} {context} {child}".strip()
    else:
        verb = {"GET": "List", "POST": "Create", "PUT": "Update", "PATCH": "Partial Update", "DELETE": "Delete"}.get(method, method.title())
        name = f"{verb} {context} {child}".strip()
    return name


# --------------------------------------------------------------------------
# Body / query param generation
# --------------------------------------------------------------------------

def example_value_for_drf_field(finfo: dict):
    t = finfo.get("type")
    if finfo.get("default") not in (None, ""):
        return finfo["default"]
    choices = finfo.get("choices")
    if choices:
        return choices[0][0]
    if t in ("integer", "id"):
        return 1
    if t in ("float", "decimal"):
        return 1.0
    if t == "boolean":
        return False
    if t == "datetime":
        return "2024-01-01T00:00:00Z"
    if t in ("field", "nested object", "object"):
        return {}
    if t == "list":
        return []
    return ""


def build_drf_body(field_schema):
    """Build a write body from a DRF OPTIONS `actions[method]` field schema.
    Some DAB-based APIs (gateway, metrics) don't expose field schemas via
    OPTIONS at all -- fall back to an empty object so the request still has
    a JSON body to fill in, rather than silently omitting one."""
    if not isinstance(field_schema, dict) or not field_schema:
        return {}
    body = {}
    for fname, finfo in field_schema.items():
        if not isinstance(finfo, dict) or finfo.get("read_only"):
            continue
        body[fname] = example_value_for_drf_field(finfo)
    return body


def resolve_ref(ref: str, components: dict):
    if not ref.startswith("#/"):
        return None
    parts = ref[2:].split("/")
    node = {"components": components}
    cur = node
    for p in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur


def example_from_schema(schema, components, depth=0, seen=None):
    if seen is None:
        seen = frozenset()
    if depth > 5 or not isinstance(schema, dict):
        return None
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref in seen:
            return None
        resolved = resolve_ref(ref, components)
        return example_from_schema(resolved, components, depth + 1, seen | {ref})
    if "example" in schema:
        return schema["example"]
    if "default" in schema:
        return schema["default"]
    t = schema.get("type")
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        out = {}
        for k, v in props.items():
            if isinstance(v, dict) and v.get("readOnly"):
                continue
            out[k] = example_from_schema(v, components, depth + 1, seen)
        return out
    if t == "array":
        val = example_from_schema(schema.get("items", {}), components, depth + 1, seen)
        return [val] if val is not None else []
    if t == "string":
        if schema.get("enum"):
            return schema["enum"][0]
        fmt = schema.get("format")
        if fmt == "date-time":
            return "2024-01-01T00:00:00Z"
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        return ""
    if t == "integer":
        return 0
    if t == "number":
        return 0
    if t == "boolean":
        return False
    for key in ("oneOf", "anyOf", "allOf"):
        if schema.get(key):
            return example_from_schema(schema[key][0], components, depth + 1, seen)
    return None


def build_openapi_body(operation: dict, components: dict):
    rb = operation.get("requestBody")
    if not isinstance(rb, dict):
        return None
    content = rb.get("content", {})
    json_content = content.get("application/json")
    if not isinstance(json_content, dict):
        return None
    example = json_content.get("example")
    if example is None:
        examples = json_content.get("examples")
        if isinstance(examples, dict) and examples:
            first = next(iter(examples.values()))
            if isinstance(first, dict):
                example = first.get("value")
    if example is None and "schema" in json_content:
        example = example_from_schema(json_content["schema"], components)
    return example


def build_query_params(operation: dict):
    if not isinstance(operation, dict):
        return []
    out = []
    for p in operation.get("parameters", []):
        if not isinstance(p, dict) or p.get("in") != "query":
            continue
        schema = p.get("schema", {}) if isinstance(p.get("schema"), dict) else {}
        val = schema.get("default", p.get("example", ""))
        out.append({
            "key": p.get("name", ""),
            "value": "" if val is None else str(val),
            "description": p.get("description", "") or "",
            "disabled": True,
        })
    return out


def build_body(method: str, meta, engine: str, components: dict):
    if method not in ("POST", "PUT", "PATCH"):
        return None
    if engine == "drf":
        return build_drf_body(meta)
    return build_openapi_body(meta, components) if isinstance(meta, dict) else None


# --------------------------------------------------------------------------
# File writing
# --------------------------------------------------------------------------

def ensure_top_level_collection():
    """Single collection ('AAP') owning auth + the base-url variable, so every
    per-API folder beneath it inherits them instead of redeclaring auth six
    times."""
    dump_yaml(TOP_LEVEL_DIR / ".resources" / "definition.yaml", {
        "$kind": "collection",
        "name": TOP_LEVEL_NAME,
        "description": (
            "Ansible Automation Platform (ansible.autodotes.com). One folder per "
            "federated top-level API discovered at /api/ (gateway, controller, eda, "
            "galaxy, lightspeed, metrics). Auth and base URL are scoped here so every "
            "nested request inherits them."
        ),
        "variables": [{"key": "aap_base_url", "value": REAL_BASE}],
        "auth": {"type": "bearer", "credentials": [{"key": "token", "value": TOKEN_VAR}]},
    })


def write_api_folder_definition(api_dir: Path, display_name: str, description: str):
    """Per-API folder metadata only -- no auth/variables here, they're
    inherited from the top-level AAP collection."""
    dump_yaml(api_dir / ".resources" / "definition.yaml", {
        "$kind": "collection",
        "name": display_name,
        "description": description,
    })


_folder_defs_written: set = set()


def ensure_folder_definitions(collection_dir: Path, folder_segs: list):
    cur = collection_dir
    for seg in folder_segs:
        cur = cur / seg
        key = str(cur)
        if key in _folder_defs_written:
            continue
        _folder_defs_written.add(key)
        def_path = cur / ".resources" / "definition.yaml"
        if not def_path.exists():
            dump_yaml(def_path, {"$kind": "collection", "name": titleize(seg)})


def write_request(collection_dir: Path, folder_segs: list, name: str, method: str, url: str,
                   path_vars: list, query_params: list, body, order: int, used_names: set):
    folder_dir = collection_dir
    for seg in folder_segs:
        folder_dir = folder_dir / seg
    folder_dir.mkdir(parents=True, exist_ok=True)
    ensure_folder_definitions(collection_dir, folder_segs)

    base_fname = sanitize_filename(name) or "request"
    fname = base_fname
    i = 2
    key = (str(folder_dir), fname.lower())
    while key in used_names:
        fname = f"{base_fname} {i}"
        key = (str(folder_dir), fname.lower())
        i += 1
    used_names.add(key)

    data = {"$kind": "http-request", "method": method, "url": url, "order": order}
    if path_vars:
        data["pathVariables"] = path_vars
    if query_params:
        data["queryParams"] = query_params
    if body is not None:
        data["headers"] = [{"key": "Content-Type", "value": "application/json"}]
        data["body"] = {"type": "json", "content": json.dumps(body, indent=2, default=str)}

    dump_yaml(folder_dir / f"{fname}.request.yaml", data)


# --------------------------------------------------------------------------
# Emission (shared across all engines)
# --------------------------------------------------------------------------

def emit_collection(collection_dir: Path, strip_prefix: str, endpoints: dict, components: dict) -> int:
    used_names: set = set()
    order = 1000
    count = 0
    for template, ep in sorted(endpoints.items(), key=lambda kv: kv[0]):
        full = ep.path
        if not full.startswith(strip_prefix):
            continue
        suffix = full[len(strip_prefix):]
        raw_segs = [s for s in suffix.split("/") if s]
        if not raw_segs:
            continue
        folder_segs = [s for s in raw_segs if not PARAM_RE.match(s)]
        if not folder_segs:
            continue

        url = BASE_VAR + strip_prefix + PARAM_RE.sub(lambda m: ":" + m.group(1), full[len(strip_prefix):])
        names_seen = set()
        path_vars = []
        for pname in PARAM_RE.findall(full):
            if pname in names_seen:
                continue
            names_seen.add(pname)
            path_vars.append({"key": pname, "value": "1" if pname == "id" else pname})

        fs_folder_segs = [sanitize_folder_segment(s) for s in folder_segs]
        for method, meta in sorted(ep.methods.items()):
            if method in ("HEAD", "OPTIONS"):
                continue
            name = build_display_name(raw_segs, folder_segs, method)
            body = build_body(method, meta, ep.engine, components)
            qp = build_query_params(meta) if ep.engine == "openapi" else []
            write_request(collection_dir, fs_folder_segs, name, method, url, path_vars, qp, body, order, used_names)
            order += 1000
            count += 1
    return count


def generate_unavailable_collection(api_dir: Path, display_name: str, probed_paths: list):
    write_api_folder_definition(
        api_dir, display_name,
        "Lightspeed is not deployed/enabled on this AAP instance: every probed path under "
        "/api/lightspeed/ returned 404 during the crawl. This placeholder documents that finding; "
        "re-run scripts/crawl_aap_api.py lightspeed once the service is enabled.",
    )
    used_names = set()
    write_request(
        api_dir, [], "Check Lightspeed Availability", "GET",
        f"{BASE_VAR}/api/lightspeed/", [], [], None, 1000, used_names,
    )
    for p in probed_paths:
        pass  # documented in the description above; no further requests needed


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

APIS = {
    "gateway": {"display": "Gateway API", "engine": "drf", "probe": "/api/gateway/"},
    "controller": {"display": "Controller API", "engine": "drf", "probe": "/api/controller/"},
    "metrics": {"display": "Metrics API", "engine": "drf", "probe": "/api/metrics/"},
    "eda": {"display": "EDA API", "engine": "openapi_eda",
            "spec_url": "/api/eda/v1/openapi.json", "server_prefix": "/api/eda/v1"},
    "galaxy": {"display": "Galaxy API", "engine": "openapi_galaxy",
               "specs": ["/api/galaxy/v3/openapi.json", "/api/galaxy/pulp/api/v3/docs/api.json"],
               "prefix": "/api/galaxy"},
    "lightspeed": {"display": "Lightspeed API", "engine": "unavailable"},
}


def run_api(key: str) -> dict:
    api = APIS[key]
    display = api["display"]
    api_dir = TOP_LEVEL_DIR / display
    print(f"\n=== {display} ===")

    if api["engine"] == "unavailable":
        generate_unavailable_collection(api_dir, display, ["/api/lightspeed/", "/api/lightspeed/v1/",
                                                             "/api/lightspeed/v0/", "/api/lightspeed/health/"])
        return {"endpoints": 0, "note": "service not deployed (404 on all probed paths)"}

    if api["engine"] == "drf":
        version_root = discover_version_root(api["probe"])
        if not version_root:
            print(f"  ! could not discover version root for {key}", file=sys.stderr)
            return {"endpoints": 0, "note": "could not discover version root"}
        endpoints = crawl_drf(version_root, key)
        write_api_folder_definition(
            api_dir, display,
            f"Crawled from {version_root} on {time.strftime('%Y-%m-%d')} via breadth-first discovery "
            "of `related` links; HTTP methods per endpoint confirmed via OPTIONS.",
        )
        n = emit_collection(api_dir, version_root.rstrip("/"), endpoints, {})
        return {"endpoints": n, "version_root": version_root}

    if api["engine"] == "openapi_eda":
        endpoints, components = load_openapi_endpoints_eda(api["spec_url"], api["server_prefix"])
        write_api_folder_definition(api_dir, display, f"Generated from {api['spec_url']}")
        n = emit_collection(api_dir, api["server_prefix"], endpoints, components)
        return {"endpoints": n}

    if api["engine"] == "openapi_galaxy":
        endpoints, components = load_openapi_endpoints_galaxy(api["specs"])
        write_api_folder_definition(
            api_dir, display,
            "Merged from /api/galaxy/v3/openapi.json and the underlying Pulp app's "
            "/api/galaxy/pulp/api/v3/docs/api.json. Pulp's dynamic {xxx_href}action/ paths "
            "(which require an already-fetched resource href rather than a fixed URL) are excluded.",
        )
        n = emit_collection(api_dir, api["prefix"], endpoints, components)
        return {"endpoints": n}

    return {"endpoints": 0, "note": f"unknown engine {api['engine']}"}


def main():
    TOP_LEVEL_DIR.mkdir(parents=True, exist_ok=True)
    ensure_top_level_collection()
    keys = sys.argv[1:] or list(APIS.keys())
    unknown = [k for k in keys if k not in APIS]
    if unknown:
        sys.exit(f"Unknown API key(s): {unknown}. Valid: {list(APIS.keys())}")

    summary = {}
    for key in keys:
        summary[key] = run_api(key)

    print("\n=== Summary ===")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
