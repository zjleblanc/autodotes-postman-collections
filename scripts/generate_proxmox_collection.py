#!/usr/bin/env python3
"""Generate a Postman v3 collection from the Proxmox VE API schema.

Downloads the Proxmox API Viewer's schema bundle (apidoc.js), extracts the
embedded `apiSchema` JSON tree, and walks it to emit one `.request.yaml`
per method+path and one `.resources/definition.yaml` per folder, following
this repo's collection-schema-v3 conventions.

Standard library only -- no third-party dependencies, so this script can be
rerun anywhere without installing anything.

Usage:
    python3 scripts/generate_proxmox_collection.py
    python3 scripts/generate_proxmox_collection.py --source /path/to/apidoc.js
    python3 scripts/generate_proxmox_collection.py --output postman/collections/Proxmox
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

APIDOC_URL = "https://pve.proxmox.com/pve-docs/api-viewer/apidoc.js"
DEFAULT_OUTPUT = "postman/collections/Proxmox"
DEFAULT_CACHE = "scripts/.cache/apidoc.js"

METHOD_ORDER = {"GET": 0, "POST": 1, "PUT": 2, "PATCH": 3, "DELETE": 4}

GENERIC_ACTIONS = {
    "index": ("List", "plural"),
    "list": ("List", "plural"),
    "create": ("Create", "singular"),
    "read": ("Get", "singular"),
    "get": ("Get", "singular"),
    "update": ("Update", "singular"),
    "set": ("Update", "singular"),
    "delete": ("Delete", "singular"),
}

# Words that read better left unpluralized/unsingularized (mass nouns, or
# Proxmox resource names that are naturally singular even in list contexts).
INVARIANT_WORDS = {"storage", "hardware", "status", "config", "firewall"}

ACRONYMS = {
    "sdn": "SDN", "ha": "HA", "acme": "ACME", "acl": "ACL", "tfa": "TFA",
    "qemu": "QEMU", "lxc": "LXC", "pci": "PCI", "usb": "USB", "dns": "DNS",
    "cpu": "CPU", "oci": "OCI", "vnc": "VNC", "rrd": "RRD", "apt": "APT",
    "ip": "IP", "id": "ID", "url": "URL", "lvm": "LVM", "zfs": "ZFS",
    "nfs": "NFS", "smb": "SMB", "ldap": "LDAP", "oidc": "OIDC", "csrf": "CSRF",
    "ssh": "SSH", "api": "API", "json": "JSON", "vm": "VM", "vms": "VMs",
    "fsinfo": "FS Info", "osinfo": "OS Info",
}

FILENAME_UNSAFE = re.compile(r'[\/\\:\*\?"<>\|]')
VARIABLE_SEGMENT = re.compile(r"^\{[^}]+\}$")
PATH_VAR_PATTERN = re.compile(r"\{([^}]+)\}")


# --------------------------------------------------------------------------
# Schema fetch + extraction
# --------------------------------------------------------------------------

def fetch_apidoc_text(source: str | None, cache_path: Path) -> str:
    if source:
        return Path(source).read_text()
    try:
        with urllib.request.urlopen(APIDOC_URL, timeout=30) as resp:
            text = resp.read().decode("utf-8")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(text)
        return text
    except Exception as exc:  # noqa: BLE001
        if cache_path.exists():
            print(f"warning: download failed ({exc}); using cached {cache_path}", file=sys.stderr)
            return cache_path.read_text()
        raise


def extract_api_schema(js_text: str) -> list:
    marker = "const apiSchema = "
    start = js_text.index(marker) + len(marker)
    depth = 0
    in_string = False
    escape = False
    end = start
    for i in range(start, len(js_text)):
        c = js_text[i]
        if escape:
            escape = False
            continue
        if c == "\\" and in_string:
            escape = True
            continue
        if c == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if c in "[{":
            depth += 1
        elif c in "]}":
            depth -= 1
            if depth == 0:
                end = i
                break
    return json.loads(js_text[start:end + 1])


# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

def is_variable(text: str) -> bool:
    return bool(VARIABLE_SEGMENT.match(text))


def humanize_word(word: str) -> str:
    lw = word.lower()
    if lw in ACRONYMS:
        return ACRONYMS[lw]
    return word[:1].upper() + word[1:] if word else word


def humanize(segment: str) -> str:
    parts = re.split(r"[-_]", segment)
    return " ".join(humanize_word(p) for p in parts if p)


def pluralize(word: str) -> str:
    lw = word.lower()
    if lw in INVARIANT_WORDS or word.endswith("s"):
        return word
    if word.endswith("y") and len(word) > 1 and word[-2].lower() not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def singularize(word: str) -> str:
    lw = word.lower()
    if lw in INVARIANT_WORDS:
        return word
    if word.endswith("ies") and len(word) > 3:
        return word[:-3] + "y"
    if word.endswith("ses") and len(word) > 3:
        return word[:-2]
    if word.endswith("s") and not word.endswith("ss") and len(word) > 1:
        return word[:-1]
    return word


def sanitize_filename(name: str) -> str:
    return FILENAME_UNSAFE.sub("-", name).strip()


def request_name(method: str, minfo: dict, own_label: str) -> str:
    name = (minfo.get("name") or method.lower()).strip()
    key = name.lower()
    if key in GENERIC_ACTIONS:
        verb, number = GENERIC_ACTIONS[key]
        resource = pluralize(own_label) if number == "plural" else singularize(own_label)
        return f"{verb} {resource}"
    return humanize(name)


def dedupe_name(candidate: str, method: str, used_lower: set[str]) -> str:
    if candidate.lower() not in used_lower:
        used_lower.add(candidate.lower())
        return candidate
    alt = f"{candidate} ({method.title()})"
    if alt.lower() not in used_lower:
        used_lower.add(alt.lower())
        return alt
    n = 2
    while True:
        alt2 = f"{alt} #{n}"
        if alt2.lower() not in used_lower:
            used_lower.add(alt2.lower())
            return alt2
        n += 1


# --------------------------------------------------------------------------
# Parameter -> value helpers
# --------------------------------------------------------------------------

def default_value_for(prop: dict):
    t = prop.get("type")
    if "default" in prop:
        d = prop["default"]
        if t == "boolean" and not isinstance(d, bool):
            return bool(d)
        return d
    enum = prop.get("enum")
    if enum:
        return enum[0]
    if t == "boolean":
        return False
    if t in ("integer", "number"):
        return 0
    if t == "array":
        return []
    if t == "object":
        return {}
    return ""


def query_value_str(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    return str(value)


def build_description(minfo: dict) -> str:
    desc = (minfo.get("description") or "").strip()
    perms = minfo.get("permissions") or {}
    perm_desc = (perms.get("description") or "").strip()
    if perm_desc:
        desc = f"{desc} Permissions: {perm_desc}".strip() if desc else f"Permissions: {perm_desc}"
    return desc


# --------------------------------------------------------------------------
# Minimal YAML emitter (hand-rolled to keep this script dependency-free and
# to match collection-schema-v3's exact quoting/style rules).
# --------------------------------------------------------------------------

BOOL_LIKE = {"true", "false", "yes", "no", "on", "off", "null", "~"}
NUMBER_LIKE = re.compile(r"^-?\d+(\.\d+)?$")
SPECIAL_CHARS = re.compile(r'[:#&*!\[\]{}>|]')


def yaml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if value is None:
        return "''"
    s = str(value)
    if s == "":
        return "''"
    needs_quote = (
        s.startswith("{{")
        or SPECIAL_CHARS.search(s) is not None
        or s.lower() in BOOL_LIKE
        or NUMBER_LIKE.match(s) is not None
        or s != s.strip()
        or s[0] in "'\"-?@`%&*"
    )
    if needs_quote:
        return "'" + s.replace("'", "''") + "'"
    return s


def emit_yaml(data: dict, indent: int = 0) -> list[str]:
    lines: list[str] = []
    pad = "  " * indent
    for key, value in data.items():
        if value is None:
            continue
        if isinstance(value, dict):
            if not value:
                lines.append(f"{pad}{key}: {{}}")
                continue
            lines.append(f"{pad}{key}:")
            lines.extend(emit_yaml(value, indent + 1))
        elif isinstance(value, list):
            if not value:
                continue
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    sub_lines = emit_yaml(item, indent + 2)
                    prefix_len = len("  " * (indent + 2))
                    first = sub_lines[0][prefix_len:]
                    lines.append(f"{pad}  - {first}")
                    lines.extend(sub_lines[1:])
                else:
                    lines.append(f"{pad}  - {yaml_scalar(item)}")
        elif isinstance(value, str) and "\n" in value:
            lines.append(f"{pad}{key}: |-")
            for line in value.split("\n"):
                lines.append(f"{pad}  {line}" if line else "")
        else:
            lines.append(f"{pad}{key}: {yaml_scalar(value)}")
    return lines


def dump_yaml(data: dict) -> str:
    return "\n".join(emit_yaml(data)) + "\n"


# --------------------------------------------------------------------------
# Request file construction
# --------------------------------------------------------------------------

def build_request_content(node_path: str, method: str, minfo: dict, order: int) -> dict:
    path_vars = PATH_VAR_PATTERN.findall(node_path)
    properties = (minfo.get("parameters") or {}).get("properties") or {}
    url = "{{base_url}}/" + "/".join(
        f":{seg[1:-1]}" if is_variable(seg) else seg
        for seg in node_path.strip("/").split("/")
    )

    content: dict = {"$kind": "http-request"}
    desc = build_description(minfo)
    if desc:
        content["description"] = desc
    content["url"] = url
    content["method"] = method

    headers = []
    extra_props = {k: v for k, v in properties.items() if k not in path_vars}
    sorted_extra = sorted(extra_props.items(), key=lambda kv: (bool(kv[1].get("optional")), kv[0]))

    if path_vars:
        path_var_entries = []
        for var in path_vars:
            prop = properties.get(var, {})
            entry = {"key": var, "value": query_value_str(default_value_for(prop)) if prop else ""}
            if prop.get("description"):
                entry["description"] = prop["description"]
            path_var_entries.append(entry)
        content["pathVariables"] = path_var_entries

    if method == "GET":
        if sorted_extra:
            query_entries = []
            for key, prop in sorted_extra:
                entry = {"key": key, "value": query_value_str(default_value_for(prop))}
                if prop.get("description"):
                    entry["description"] = prop["description"]
                # Keep all query params disabled by default (matching this repo's
                # convention, e.g. AO/Settings/List Settings.request.yaml) so the
                # URL itself stays query-string-free and doesn't need to be kept
                # in sync with every optional/required filter.
                entry["disabled"] = True
                query_entries.append(entry)
            content["queryParams"] = query_entries
    else:
        if sorted_extra:
            body_obj = {key: default_value_for(prop) for key, prop in sorted_extra}
            headers.append({"key": "Content-Type", "value": "application/json"})
            content["body"] = {"type": "json", "content": json.dumps(body_obj, indent=2)}

    if headers:
        content["headers"] = headers

    content["settings"] = {}
    content["order"] = order
    return content


def apply_special_overrides(node_path: str, method: str, content: dict) -> None:
    """Hand-authored overrides for the auth bootstrap endpoint, mirroring
    this repo's AO/Auth/Login.request.yaml convention (noauth + a script
    that captures the resulting session values)."""
    if node_path == "/access/ticket" and method == "POST":
        content["auth"] = {"type": "noauth"}
        content["scripts"] = [{
            "type": "afterResponse",
            "language": "text/javascript",
            "code": (
                "if (pm.response.code === 200) {\n"
                "    const data = (pm.response.json() || {}).data || {};\n"
                "    if (data.ticket) { pm.collectionVariables.set('pve_ticket', data.ticket); }\n"
                "    if (data.CSRFPreventionToken) { pm.collectionVariables.set('csrf_token', data.CSRFPreventionToken); }\n"
                "}"
            ),
        }]


# --------------------------------------------------------------------------
# Tree walk
# --------------------------------------------------------------------------

class Generator:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.order_counters: dict[Path, int] = {}
        self.used_names: dict[Path, set[str]] = {}
        self.folder_count = 0
        self.request_count = 0

    def next_order(self, directory: Path) -> int:
        current = self.order_counters.get(directory, 0) + 1000
        self.order_counters[directory] = current
        return current

    def used_set(self, directory: Path) -> set[str]:
        return self.used_names.setdefault(directory, set())

    def write_request(self, directory: Path, name: str, content: dict) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        filename = sanitize_filename(name) + ".request.yaml"
        (directory / filename).write_text(dump_yaml(content))
        self.request_count += 1

    def write_folder_definition(self, directory: Path, order: int) -> None:
        resources_dir = directory / ".resources"
        resources_dir.mkdir(parents=True, exist_ok=True)
        content = {"$kind": "collection", "order": order}
        (resources_dir / "definition.yaml").write_text(dump_yaml(content))
        self.folder_count += 1

    def process_node(self, node: dict, out_dir: Path, parent_label: str | None) -> None:
        text = node.get("text", "")
        node_path = node.get("path", "")
        children = node.get("children") or []
        variable = is_variable(text)

        if variable:
            own_label = parent_label or humanize(text.strip("{}"))
            own_dir = out_dir
        else:
            own_label = humanize(text)
            if children:
                own_dir = out_dir / sanitize_filename(own_label)
                order = self.next_order(out_dir)
                self.write_folder_definition(own_dir, order)
            else:
                own_dir = out_dir

        info = node.get("info") or {}
        for method in sorted(info.keys(), key=lambda m: METHOD_ORDER.get(m, 99)):
            minfo = info[method]
            order = self.next_order(own_dir)
            content = build_request_content(node_path, method, minfo, order)
            apply_special_overrides(node_path, method, content)
            candidate = request_name(method, minfo, own_label)
            final_name = dedupe_name(candidate, method, self.used_set(own_dir))
            self.write_request(own_dir, final_name, content)

        for child in children:
            self.process_node(child, own_dir, own_label)

    def run(self, schema: list) -> None:
        self.output_root.mkdir(parents=True, exist_ok=True)
        for node in schema:
            self.process_node(node, self.output_root, None)


# --------------------------------------------------------------------------
# Collection-level definition.yaml
# --------------------------------------------------------------------------

COLLECTION_DEFINITION = {
    "$kind": "collection",
    "name": "Proxmox",
    "description": (
        "Proxmox VE REST API. Manages cluster, nodes, VMs (QEMU/LXC), storage, access control, "
        "and pools. Generated from the official API schema at "
        "https://pve.proxmox.com/pve-docs/api-viewer/index.html. Authenticate via "
        "Access > Create Ticket (sets pve_ticket/csrf_token automatically), or replace this "
        "collection's auth with an API token header for long-lived automation."
    ),
    "variables": [
        {"key": "base_url", "value": "https://localhost:8006/api2/json",
         "description": "Proxmox VE API base URL (scheme + host + port + /api2/json)"},
        {"key": "pve_ticket", "value": "",
         "description": "PVEAuthCookie ticket value, set automatically by Access > Create Ticket"},
        {"key": "csrf_token", "value": "",
         "description": "CSRFPreventionToken, set automatically by Access > Create Ticket; required on non-GET requests"},
    ],
    "auth": {
        "type": "apikey",
        "credentials": [
            {"key": "key", "value": "Cookie"},
            {"key": "value", "value": "PVEAuthCookie={{pve_ticket}}"},
            {"key": "in", "value": "header"},
        ],
    },
    "scripts": [{
        "type": "http:beforeRequest",
        "language": "text/javascript",
        "code": (
            "if (pm.collectionVariables.get('csrf_token') && pm.request.method !== 'GET') {\n"
            "    pm.request.headers.upsert({ key: 'CSRFPreventionToken', value: pm.collectionVariables.get('csrf_token') });\n"
            "}"
        ),
    }],
}


def write_collection_definition(output_root: Path) -> None:
    resources_dir = output_root / ".resources"
    resources_dir.mkdir(parents=True, exist_ok=True)
    (resources_dir / "definition.yaml").write_text(dump_yaml(COLLECTION_DEFINITION))


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Local path to an already-downloaded apidoc.js (skips network fetch)")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="Output collection directory")
    parser.add_argument("--cache", default=DEFAULT_CACHE, help="Cache path for the downloaded apidoc.js")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    output_root = (repo_root / args.output) if not Path(args.output).is_absolute() else Path(args.output)
    cache_path = (repo_root / args.cache) if not Path(args.cache).is_absolute() else Path(args.cache)

    js_text = fetch_apidoc_text(args.source, cache_path)
    schema = extract_api_schema(js_text)

    write_collection_definition(output_root)

    gen = Generator(output_root)
    gen.run(schema)

    print(f"Wrote {gen.request_count} requests across {gen.folder_count} folders to {output_root}")


if __name__ == "__main__":
    main()
