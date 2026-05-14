#!/usr/bin/env python3
"""
Build production-plugins-registry.json from live BioThings GitHub repos.

Read-only: fetches raw file content via GitHub API. Never modifies the upstream repos.

Usage:
    python build_production_registry.py [--output PATH] [--token GITHUB_TOKEN]

Environment:
    GITHUB_TOKEN  — optional; raises rate limit from 60 to 5000 req/hr.
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Config: repos and their plugin directories
# ---------------------------------------------------------------------------
REPOS = [
    {"owner": "biothings", "repo": "pending.api",      "path": "plugins",         "branch": "master"},
    {"owner": "biothings", "repo": "mydisease.info",    "path": "src/plugins",     "branch": "master"},
    {"owner": "biothings", "repo": "mychem.info",       "path": "src/plugins",     "branch": "master"},
    {"owner": "biothings", "repo": "mygene.info",       "path": "src/plugins",     "branch": "master"},
    {"owner": "biothings", "repo": "myvariant.info",    "path": "src/plugins",     "branch": "master"},
]

# Files we care about inside each plugin directory
PLUGIN_FILES = [
    "manifest.json",
    "manifest.yaml",
    "parser.py",
    "parse.py",
    "version.py",
    "mapping.py",
    "dumper.py",
    "uploader.py",
    "README.md",
    "README",
]

# Target API inference from repo name
REPO_TO_API = {
    "pending.api":      "pending.api",
    "mydisease.info":   "MyDisease.info",
    "mychem.info":      "MyChem.info",
    "mygene.info":      "MyGene.info",
    "myvariant.info":   "MyVariant.info",
}

# ---------------------------------------------------------------------------
# GitHub API helpers
# ---------------------------------------------------------------------------
def github_get_json(url, token=None, retries=3):
    """GET a GitHub API URL, return parsed JSON."""
    headers = {"Accept": "application/vnd.github.v3+json", "User-Agent": "biothings-registry-builder"}
    if token:
        headers["Authorization"] = f"token {token}"

    for attempt in range(retries):
        try:
            req = Request(url, headers=headers)
            with urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            if e.code == 403:
                reset = int(e.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset - int(time.time()), 10)
                print(f"  [rate-limited] waiting {wait}s...", file=sys.stderr)
                time.sleep(wait)
            elif e.code == 404:
                return None
            else:
                if attempt == retries - 1:
                    raise
                time.sleep(2 ** attempt)
    return None


def fetch_raw_file(owner, repo, branch, filepath, token=None):
    """Fetch raw file content from raw.githubusercontent.com (NOT rate-limited)."""
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{filepath}"
    try:
        headers = {"User-Agent": "biothings-registry-builder"}
        if token:
            headers["Authorization"] = f"token {token}"
        req = Request(url, headers=headers)
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except HTTPError:
        return None


def get_repo_tree(owner, repo, branch, token=None):
    """Fetch the ENTIRE repo file tree in a single API call.

    This is the key optimization: 1 API call per repo instead of 1 per plugin directory.
    Returns a dict mapping file paths to sizes.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    data = github_get_json(url, token)
    if not data or "tree" not in data:
        return {}
    return {item["path"]: item.get("size", 0) for item in data["tree"] if item["type"] == "blob"}


def extract_plugins_from_tree(tree, plugin_base_path):
    """Given a full repo tree and the base path (e.g. 'plugins'), return
    a dict of {plugin_name: {filename: size}} for each plugin subdirectory."""
    plugins = {}
    prefix = plugin_base_path.rstrip("/") + "/"
    for filepath, size in tree.items():
        if not filepath.startswith(prefix):
            continue
        rest = filepath[len(prefix):]
        parts = rest.split("/")
        if len(parts) == 2:  # plugin_name/filename
            plugin_name, filename = parts
            plugins.setdefault(plugin_name, {})[filename] = size
    return plugins


# ---------------------------------------------------------------------------
# Pattern classification
# ---------------------------------------------------------------------------
def classify_parser_pattern(parser_code, manifest_data, files_present):
    """Classify the parser pattern from code content."""
    if not parser_code:
        if "dumper.py" in files_present or "uploader.py" in files_present:
            return ["custom_dumper_uploader"]
        return ["unknown"]

    patterns = []

    # Check for HGVS generation
    if "get_hgvs_from_vcf" in parser_code or "hgvs" in parser_code.lower():
        patterns.append("hgvs_variant")

    # Check for VCF parsing
    if "import vcf" in parser_code or "VCF" in parser_code:
        patterns.append("vcf_parsing")

    # Check for pandas
    if "import pandas" in parser_code or "pd.read_csv" in parser_code or "pd.read_excel" in parser_code:
        patterns.append("pandas")

    # Check for groupby
    if "groupby" in parser_code:
        if "itertools" in parser_code or "from itertools" in parser_code:
            patterns.append("itertools_groupby")
        if "df.groupby" in parser_code or ".groupby(" in parser_code:
            patterns.append("pandas_groupby")

    # Check for cross-API resolution
    if "biothings_client" in parser_code or "get_client" in parser_code:
        patterns.append("cross_api_resolution")

    # Check for merge_duplicate_rows
    if "merge_duplicate_rows" in parser_code:
        patterns.append("merge_duplicates")

    # Check for multi-file glob
    if "glob.glob" in parser_code or "import glob" in parser_code:
        patterns.append("multi_file_glob")

    # Check for orjson
    if "orjson" in parser_code:
        patterns.append("orjson_json")
    elif "json.load" in parser_code or "json.loads" in parser_code:
        patterns.append("json_parsing")

    # Check for NDJSON
    if "ndjson" in parser_code.lower() or "jsonlines" in parser_code.lower():
        patterns.append("ndjson")

    # Check for open_anyfile (gzip handling)
    if "open_anyfile" in parser_code:
        patterns.append("gzip_open_anyfile")

    # Check for csv.DictReader
    if "DictReader" in parser_code or "csv.reader" in parser_code:
        patterns.append("csv_reader")

    # Check for subject/object/relation triple
    if '"subject"' in parser_code and '"object"' in parser_code:
        patterns.append("subject_object_triple")

    # Check for OBO shared parser (in manifest, not parser.py)
    if manifest_data and isinstance(manifest_data, dict):
        uploader = manifest_data.get("uploader", {})
        parser_ref = uploader.get("parser", "")
        if "hub.dataload.data_parsers" in parser_ref:
            patterns.append("shared_hub_parser")

    if not patterns:
        patterns.append("simple_streaming")

    return patterns


def classify_version_pattern(version_code):
    """Classify the version.py strategy."""
    if not version_code:
        return "none"

    if "requests" in version_code and "Last-Modified" in version_code:
        return "http_last_modified"
    elif "requests" in version_code and ".json()" in version_code:
        return "api_endpoint"
    elif "requests" in version_code:
        return "http_dynamic"
    elif "return" in version_code:
        # Check if it's a hardcoded string
        match = re.search(r'return\s+["\']([^"\']+)["\']', version_code)
        if match:
            return "hardcoded"
    return "other"


def extract_id_strategy(parser_code, manifest_data):
    """Try to infer the _id strategy from parser code."""
    if not parser_code:
        return "unknown"

    if "get_hgvs_from_vcf" in parser_code:
        return "HGVS"
    if "InChIKey" in parser_code or "inchikey" in parser_code.lower() or "inchi_key" in parser_code.lower():
        return "InChIKey"

    # Look for composite _id patterns
    if re.search(r'f"[^"]*\{[^}]+\}[^"]*\{[^}]+\}"', parser_code):
        return "composite"

    # Look for _id assignment
    id_match = re.search(r'"_id"\s*:\s*(\w+)', parser_code)
    if id_match:
        var_name = id_match.group(1)
        if var_name == "HGVS":
            return "HGVS"
        return f"field:{var_name}"

    return "inferred_from_code"


def extract_requires(manifest_data):
    """Extract requires list from manifest."""
    if not manifest_data:
        return []
    requires = manifest_data.get("requires", [])
    if isinstance(requires, str):
        return [requires]
    return requires or []


def extract_key_techniques(parser_code):
    """Extract notable techniques/imports from parser code."""
    if not parser_code:
        return []

    techniques = []
    technique_markers = {
        "dict_sweep": "dict_sweep cleanup",
        "unlist": "unlist flattening",
        "value_convert_to_number": "numeric conversion",
        "merge_duplicate_rows": "duplicate row merging",
        "to_boolean": "boolean conversion",
        "open_anyfile": "transparent gzip handling",
        "defaultdict": "defaultdict aggregation",
        "get_client": "biothings_client cross-API query",
        "get_hgvs_from_vcf": "VCF→HGVS conversion",
        "groupby": "groupby aggregation",
        "orjson": "orjson fast JSON parsing",
        "pd.read_csv": "pandas CSV reader",
        "pd.read_excel": "pandas Excel reader",
        "tab2list": "biothings tab2list loader",
    }
    for marker, label in technique_markers.items():
        if marker in parser_code:
            techniques.append(label)
    return techniques


# ---------------------------------------------------------------------------
# Manifest parsing (JSON or YAML)
# ---------------------------------------------------------------------------
def parse_manifest(content, filename):
    """Parse manifest from JSON or YAML content string."""
    if not content:
        return None
    if filename.endswith(".yaml") or filename.endswith(".yml"):
        try:
            import yaml
            return yaml.safe_load(content)
        except ImportError:
            # Basic YAML parsing fallback for simple manifests
            print("  [warn] PyYAML not installed; skipping YAML manifest", file=sys.stderr)
            return {"_raw_yaml": content}
        except Exception:
            return {"_raw_yaml": content}
    else:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return None


# ---------------------------------------------------------------------------
# Main extraction
# ---------------------------------------------------------------------------
def extract_plugin_from_tree(owner, repo, branch, path, plugin_name, files, token=None):
    """Extract all data for a single plugin. `files` is {filename: size} from the tree.

    Only uses raw.githubusercontent.com for file content (NOT rate-limited).
    Zero GitHub API calls.
    """
    target_api = REPO_TO_API.get(repo, "unknown")

    entry = {
        "id": plugin_name,
        "repo": repo,
        "repo_url": f"https://github.com/{owner}/{repo}/tree/{branch}/{path}/{plugin_name}",
        "target_api": target_api,
        "files_present": sorted(files.keys()),
        "file_sizes": files,
    }

    base = f"{path}/{plugin_name}"

    # Manifest (try JSON first, then YAML)
    manifest_content = None
    manifest_filename = None
    for mf in ["manifest.json", "manifest.yaml", "manifest.yml"]:
        if mf in files:
            manifest_content = fetch_raw_file(owner, repo, branch, f"{base}/{mf}", token)
            manifest_filename = mf
            break

    manifest_data = parse_manifest(manifest_content, manifest_filename or "manifest.json")
    entry["manifest"] = manifest_data
    entry["manifest_format"] = "yaml" if manifest_filename and "yaml" in manifest_filename else "json"

    # Parser code
    parser_code = None
    parser_filename = None
    for pf in ["parser.py", "parse.py"]:
        if pf in files:
            parser_code = fetch_raw_file(owner, repo, branch, f"{base}/{pf}", token)
            parser_filename = pf
            break

    # Uploader (for custom dumper/uploader pattern)
    uploader_code = None
    if "uploader.py" in files:
        uploader_code = fetch_raw_file(owner, repo, branch, f"{base}/uploader.py", token)

    effective_parser = parser_code or uploader_code
    entry["parser_code"] = effective_parser
    entry["parser_filename"] = parser_filename or ("uploader.py" if uploader_code else None)

    # Version.py
    version_code = None
    if "version.py" in files:
        version_code = fetch_raw_file(owner, repo, branch, f"{base}/version.py", token)
    entry["version_code"] = version_code

    # Dumper.py
    dumper_code = None
    if "dumper.py" in files:
        dumper_code = fetch_raw_file(owner, repo, branch, f"{base}/dumper.py", token)
    entry["has_custom_dumper"] = "dumper.py" in files
    entry["dumper_code"] = dumper_code

    # Mapping.py
    entry["has_mapping_py"] = "mapping.py" in files

    # Classifications
    entry["parser_patterns"] = classify_parser_pattern(effective_parser, manifest_data, files)
    entry["version_strategy"] = classify_version_pattern(version_code)
    entry["id_strategy"] = extract_id_strategy(effective_parser, manifest_data)
    entry["requires"] = extract_requires(manifest_data)
    entry["key_techniques"] = extract_key_techniques(effective_parser)
    entry["has_version_py"] = "version.py" in files

    # Manifest-derived fields
    if manifest_data and isinstance(manifest_data, dict):
        entry["manifest_version"] = manifest_data.get("version")
        dumper = manifest_data.get("dumper", {})
        entry["data_url"] = dumper.get("data_url")
        entry["uncompress"] = dumper.get("uncompress")
        entry["has_schedule"] = "schedule" in dumper
        entry["has_release_wiring"] = "release" in dumper

        uploader = manifest_data.get("uploader", {})
        uploaders = manifest_data.get("uploaders", [])
        entry["on_duplicates"] = uploader.get("on_duplicates") if uploader else None
        entry["uses_plural_uploaders"] = bool(uploaders)
        entry["uploader_count"] = len(uploaders) if uploaders else 1

        metadata = manifest_data.get("__metadata__", {})
        entry["license"] = metadata.get("license")
        entry["license_url"] = metadata.get("license_url")
        entry["datasource_url"] = metadata.get("url")

    return entry


def build_registry(token=None):
    """Build the full registry from all repos.

    Uses the Git Trees API: 1 API call per repo to get the full file tree,
    then raw.githubusercontent.com (not rate-limited) for all file content.
    Total API calls = len(REPOS) = 5.
    """
    plugins = []
    stats = {"repos_scanned": 0, "plugins_found": 0, "plugins_extracted": 0, "api_calls": 0}

    for repo_config in REPOS:
        owner = repo_config["owner"]
        repo = repo_config["repo"]
        path = repo_config["path"]
        branch = repo_config["branch"]

        print(f"\n[{repo}] Fetching repo tree (1 API call)...", file=sys.stderr)
        stats["repos_scanned"] += 1
        stats["api_calls"] += 1

        tree = get_repo_tree(owner, repo, branch, token)
        if not tree:
            print(f"  Failed to fetch tree — skipping", file=sys.stderr)
            continue

        plugin_map = extract_plugins_from_tree(tree, path)
        if not plugin_map:
            print(f"  No plugins found under {path}/", file=sys.stderr)
            continue

        print(f"  Found {len(plugin_map)} plugins: {', '.join(sorted(plugin_map.keys()))}", file=sys.stderr)
        stats["plugins_found"] += len(plugin_map)

        for plugin_name in sorted(plugin_map.keys()):
            plugin_files = plugin_map[plugin_name]
            print(f"  Extracting {plugin_name} ({len(plugin_files)} files)...", file=sys.stderr)
            entry = extract_plugin_from_tree(owner, repo, branch, path, plugin_name, plugin_files, token)
            if entry:
                plugins.append(entry)
                stats["plugins_extracted"] += 1
            else:
                print(f"    [skip] Could not extract {plugin_name}", file=sys.stderr)

    registry = {
        "_metadata": {
            "description": "Production BioThings data plugins extracted from GitHub repos. Read-only ground truth for the biothings-plugin-generator skill.",
            "repos_scanned": [f"https://github.com/{r['owner']}/{r['repo']}" for r in REPOS],
            "plugin_count": len(plugins),
            "stats": stats,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "generator": "build_production_registry.py",
        },
        "plugins": plugins,
    }

    return registry


# ---------------------------------------------------------------------------
# Also build a compact summary (no code — just metadata for quick lookups)
# ---------------------------------------------------------------------------
def build_summary(registry):
    """Build a compact summary without code fields — for low-token reference."""
    summary_plugins = []
    for p in registry["plugins"]:
        summary_plugins.append({
            "id": p["id"],
            "repo": p["repo"],
            "target_api": p["target_api"],
            "files_present": p["files_present"],
            "parser_patterns": p["parser_patterns"],
            "version_strategy": p["version_strategy"],
            "id_strategy": p["id_strategy"],
            "requires": p["requires"],
            "key_techniques": p["key_techniques"],
            "manifest_version": p.get("manifest_version"),
            "manifest_format": p.get("manifest_format", "json"),
            "on_duplicates": p.get("on_duplicates"),
            "uses_plural_uploaders": p.get("uses_plural_uploaders", False),
            "has_custom_dumper": p.get("has_custom_dumper", False),
            "has_version_py": p.get("has_version_py", False),
            "has_mapping_py": p.get("has_mapping_py", False),
            "has_schedule": p.get("has_schedule", False),
            "has_release_wiring": p.get("has_release_wiring", False),
            "license": p.get("license"),
            "datasource_url": p.get("datasource_url"),
            "repo_url": p.get("repo_url"),
        })

    return {
        "_metadata": {
            "description": "Compact summary of production BioThings plugins — no code, just metadata for pattern matching and quick lookups. For full code, see production-plugins-registry.json.",
            "plugin_count": len(summary_plugins),
            "generated_at": registry["_metadata"]["generated_at"],
        },
        "plugins": summary_plugins,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Build production BioThings plugin registry from GitHub.")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path for full registry JSON. Default: ../references/production-plugins-registry.json")
    parser.add_argument("--summary-output", "-s", default=None,
                        help="Output path for compact summary JSON. Default: ../references/production-plugins-summary.json")
    parser.add_argument("--token", "-t", default=None,
                        help="GitHub token. Also reads GITHUB_TOKEN env var.")
    args = parser.parse_args()

    token = args.token or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("[warn] No GITHUB_TOKEN set. Rate limit is 60 requests/hour.", file=sys.stderr)
        print("       Set GITHUB_TOKEN env var or pass --token for 5000 req/hr.", file=sys.stderr)

    # Default output paths relative to this script
    script_dir = Path(__file__).parent
    refs_dir = script_dir.parent / "references"
    refs_dir.mkdir(parents=True, exist_ok=True)

    output_path = Path(args.output) if args.output else refs_dir / "production-plugins-registry.json"
    summary_path = Path(args.summary_output) if args.summary_output else refs_dir / "production-plugins-summary.json"

    # Build
    registry = build_registry(token)

    # Write full registry
    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)
    print(f"\n[done] Full registry: {output_path} ({os.path.getsize(output_path):,} bytes, {len(registry['plugins'])} plugins)", file=sys.stderr)

    # Write compact summary
    summary = build_summary(registry)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"[done] Summary: {summary_path} ({os.path.getsize(summary_path):,} bytes)", file=sys.stderr)


if __name__ == "__main__":
    main()
