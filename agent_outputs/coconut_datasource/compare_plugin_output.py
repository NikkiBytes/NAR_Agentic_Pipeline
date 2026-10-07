"""
Compare COCONUT plugin output against the source CSV, REST API, and (optionally)
a live BioThings server.

Usage:
    python compare_plugin_output.py <COCONUT_ID_or_InChIKey>

    e.g.  python compare_plugin_output.py CNP0116685.1
          python compare_plugin_output.py AOENXCFCECBJAP-PGRDOPGGSA-N

Environment variables:
    COCONUT_EMAIL      – COCONUT account email    (for REST API auth)
    COCONUT_PASSWORD   – COCONUT account password (for REST API auth)
    COCONUT_API_TOKEN  – pre-obtained Bearer token (skips login step)
    BIOTHINGS_URL      – local BioThings server base URL (default: http://localhost:9999)
    PLUGIN_NAME        – plugin name path segment  (default: coconut_plugin)

REST API discovered from: https://coconut.naturalproducts.net/vendor/rest/openapi.json
  POST /api/auth/login          – obtain Bearer token
  POST /api/molecules/search    – filter by identifier / standard_inchi_key
                                  include: [{"relation": "properties"}]
"""

import csv
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

# ── config ────────────────────────────────────────────────────────────────────
PLUGIN_DIR = Path(__file__).parent / "coconut_plugin"
CSV_PATH = (
    PLUGIN_DIR
    / ".biothings_hub/archive/coconut_plugin/202605/coconut_csv-05-2026.csv"
)
COCONUT_BASE = "https://coconut.naturalproducts.net"
BIOTHINGS_URL = os.environ.get("BIOTHINGS_URL", "http://localhost:9999")
PLUGIN_NAME = os.environ.get("PLUGIN_NAME", "coconut_plugin")

# Fields the REST API exposes that are NOT present in the bulk CSV download
API_ONLY_FIELDS = {
    "sugar_free_smiles",
    "structural_comments",
    "name_trust_level",
    "variants_count",
    "status",
    "active",
    "has_variants",
    "has_stereo",
    "is_tautomer",
    "is_parent",
    "is_placeholder",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def _post_json(url: str, payload: dict, token: str | None = None) -> dict:
    body = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Mozilla/5.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def coconut_login(email: str, password: str) -> str | None:
    """Login and return the Bearer token, or None on failure."""
    try:
        resp = _post_json(f"{COCONUT_BASE}/api/auth/login", {"email": email, "password": password})
        return resp.get("token") or resp.get("access_token") or resp.get("data", {}).get("token")
    except Exception as e:
        print(f"  Login failed: {e}")
        return None


def fetch_coconut_api(query: str, token: str) -> dict | None:
    """
    Fetch compound from COCONUT REST API using POST /api/molecules/search.
    Tries identifier first, then standard_inchi_key.
    Returns the first result's data dict (with properties included), or None.
    """
    is_inchi_key = len(query) == 27 and query[14] == "-"
    filter_field = "standard_inchi_key" if is_inchi_key else "identifier"

    payload = {
        "search": {
            "filters": [{"field": filter_field, "operator": "=", "value": query}],
            "includes": [{"relation": "properties"}],
            "page": 1,
            "limit": 1,
        }
    }
    try:
        resp = _post_json(f"{COCONUT_BASE}/api/molecules/search", payload, token)
        data = resp.get("data", [])
        return data[0] if data else None
    except urllib.error.HTTPError as e:
        print(f"  API search failed: HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  API search failed: {e}")
        return None


def find_csv_row(query: str) -> dict | None:
    """Return the raw CSV row dict matching a COCONUT ID or InChIKey."""
    with open(CSV_PATH, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row["identifier"] == query or row["standard_inchi_key"] == query:
                return row
    return None


def run_parser(row: dict) -> dict:
    """Feed a single CSV row through the real parser.py and return the BioThings doc."""
    sys.path.insert(0, str(PLUGIN_DIR))
    from parser import load_data  # noqa: PLC0415

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=row.keys())
    writer.writeheader()
    writer.writerow(row)

    with tempfile.TemporaryDirectory() as tmpdir:
        csv_file = os.path.join(tmpdir, "coconut_csv-05-2026.csv")
        with open(csv_file, "w") as f:
            f.write(buf.getvalue())
        docs = list(load_data(tmpdir))

    return docs[0] if docs else {}


def fetch_biothings(inchi_key: str) -> dict | None:
    """Fetch from the live local BioThings server. Returns None if unreachable."""
    url = f"{BIOTHINGS_URL}/{PLUGIN_NAME}/{inchi_key}"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def flatten_keys(obj, prefix="") -> set[str]:
    """Return all dot-notation key paths in a nested dict/list."""
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, (dict, list)):
                keys |= flatten_keys(v, full)
            else:
                keys.add(full)
    elif isinstance(obj, list):
        for item in obj:
            keys |= flatten_keys(item, prefix)
    return keys


def _get_token() -> str | None:
    token = os.environ.get("COCONUT_API_TOKEN")
    if token:
        return token
    email = os.environ.get("COCONUT_EMAIL")
    password = os.environ.get("COCONUT_PASSWORD")
    if email and password:
        print(f"  Logging in as {email} …")
        return coconut_login(email, password)
    return None


# ── main comparison ───────────────────────────────────────────────────────────

def compare(query: str):
    print(f"\n{'='*70}")
    print(f"  COCONUT Plugin Field Comparison")
    print(f"  Query: {query}")
    print(f"{'='*70}\n")

    # 1. Source CSV
    print("[ 1 ] Looking up row in source CSV …")
    row = find_csv_row(query)
    if not row:
        print(f"  ERROR: '{query}' not found in {CSV_PATH}")
        return
    inchi_key = row["standard_inchi_key"]
    print(f"  Found: {row['identifier']}  InChIKey={inchi_key}\n")

    # 2. Parser output
    print("[ 2 ] Running through parser.py …")
    plugin_doc = run_parser(row)
    print(f"  Done. Top-level keys under 'coconut': {sorted(plugin_doc.get('coconut', {}).keys())}\n")

    # 3. REST API
    print("[ 3 ] Querying COCONUT REST API …")
    token = _get_token()
    api_doc = None
    if token:
        api_doc = fetch_coconut_api(query, token)
        if api_doc:
            api_fields = sorted(api_doc.keys())
            print(f"  Got response. Top-level fields: {api_fields}\n")
        else:
            print("  No result returned from API.\n")
    else:
        print("  Skipped — set COCONUT_EMAIL+COCONUT_PASSWORD or COCONUT_API_TOKEN to enable.\n")
        print("  Register free at: https://coconut.naturalproducts.net/register\n")

    # 4. Live BioThings server
    print("[ 4 ] Querying live BioThings server …")
    server_doc = fetch_biothings(inchi_key)
    if server_doc:
        print(f"  Fetched from {BIOTHINGS_URL}/{PLUGIN_NAME}/{inchi_key}\n")
    else:
        print(f"  Server not reachable at {BIOTHINGS_URL} (run biothings-cli to enable)\n")

    # ── Field mapping: CSV → plugin ───────────────────────────────────────
    print("─" * 70)
    print("  SOURCE CSV  →  PLUGIN DOCUMENT  (field mapping)")
    print("─" * 70)

    CSV_TO_PLUGIN = {
        "identifier":                       "coconut.coconut_id",
        "canonical_smiles":                 "coconut.smiles",
        "standard_inchi":                   "coconut.inchi",
        "standard_inchi_key":               "_id  +  coconut.inchi_key",
        "name":                             "coconut.name",
        "iupac_name":                       "coconut.iupac_name",
        "molecular_formula":                "coconut.molecular_formula",
        "molecular_weight":                 "coconut.properties.molecular_weight",
        "exact_molecular_weight":           "coconut.properties.exact_molecular_weight",
        "alogp":                            "coconut.properties.alogp",
        "topological_polar_surface_area":   "coconut.properties.topological_polar_surface_area",
        "qed_drug_likeliness":              "coconut.properties.qed_drug_likeliness",
        "np_likeness":                      "coconut.properties.np_likeness",
        "fractioncsp3":                     "coconut.properties.fractioncsp3",
        "van_der_walls_volume":             "coconut.properties.van_der_walls_volume",
        "total_atom_count":                 "coconut.properties.total_atom_count",
        "heavy_atom_count":                 "coconut.properties.heavy_atom_count",
        "rotatable_bond_count":             "coconut.properties.rotatable_bond_count",
        "hydrogen_bond_acceptors":          "coconut.properties.hydrogen_bond_acceptors",
        "hydrogen_bond_donors":             "coconut.properties.hydrogen_bond_donors",
        "hydrogen_bond_acceptors_lipinski": "coconut.properties.hydrogen_bond_acceptors_lipinski",
        "hydrogen_bond_donors_lipinski":    "coconut.properties.hydrogen_bond_donors_lipinski",
        "lipinski_rule_of_five_violations": "coconut.properties.lipinski_rule_of_five_violations",
        "aromatic_rings_count":             "coconut.properties.aromatic_rings_count",
        "number_of_minimal_rings":          "coconut.properties.number_of_minimal_rings",
        "formal_charge":                    "coconut.properties.formal_charge",
        "contains_sugar":                   "coconut.properties.contains_sugar",
        "contains_ring_sugars":             "coconut.properties.contains_ring_sugars",
        "contains_linear_sugars":           "coconut.properties.contains_linear_sugars",
        "annotation_level":                 "coconut.properties.annotation_level",
        "murcko_framework":                 "coconut.murcko_framework",
        "chemical_class":                   "coconut.classification.chemical_class",
        "chemical_sub_class":               "coconut.classification.chemical_sub_class",
        "chemical_super_class":             "coconut.classification.chemical_super_class",
        "direct_parent_classification":     "coconut.classification.direct_parent",
        "np_classifier_pathway":            "coconut.np_classifier.pathway",
        "np_classifier_superclass":         "coconut.np_classifier.superclass",
        "np_classifier_class":              "coconut.np_classifier.class",
        "np_classifier_is_glycoside":       "coconut.np_classifier.is_glycoside",
        "organisms":                        "coconut.organisms  (pipe → list; dropped if empty)",
        "collections":                      "coconut.collections  (pipe → list; dropped if empty)",
        "synonyms":                         "coconut.synonyms  (pipe → list; dropped if empty)",
        "cas":                              "coconut.xrefs.cas  (pipe → list; dropped if empty)",
        "dois":                             "coconut.xrefs.doi  (pipe → list; dropped if empty)",
    }

    for csv_field, plugin_path in CSV_TO_PLUGIN.items():
        present = "✓" if row.get(csv_field, "") else "–"
        print(f"  {present}  {csv_field:<42}  →  {plugin_path}")

    # ── API-only fields (not in bulk CSV) ─────────────────────────────────
    print(f"\n  API-only fields (not in bulk CSV — only accessible via REST API):")
    for f in sorted(API_ONLY_FIELDS):
        api_val = api_doc.get(f, "<not fetched>") if api_doc else "<auth required>"
        print(f"  ·  {f:<30}  API value: {api_val!r}")

    # ── Value spot-check: CSV vs plugin ──────────────────────────────────
    print("\n" + "─" * 70)
    print("  VALUE SPOT-CHECK  (source CSV  vs  plugin output)")
    print("─" * 70)
    checks = [
        ("_id",                           row["standard_inchi_key"],       plugin_doc.get("_id")),
        ("coconut_id",                    row["identifier"],               plugin_doc.get("coconut", {}).get("coconut_id")),
        ("name",                          row["name"],                     plugin_doc.get("coconut", {}).get("name")),
        ("molecular_formula",             row["molecular_formula"],        plugin_doc.get("coconut", {}).get("molecular_formula")),
        ("molecular_weight",              float(row["molecular_weight"]),  plugin_doc.get("coconut", {}).get("properties", {}).get("molecular_weight")),
        ("alogp",                         float(row["alogp"]),             plugin_doc.get("coconut", {}).get("properties", {}).get("alogp")),
        ("contains_sugar",                row["contains_sugar"] == "True", plugin_doc.get("coconut", {}).get("properties", {}).get("contains_sugar")),
        ("classification.chemical_class", row["chemical_class"],           plugin_doc.get("coconut", {}).get("classification", {}).get("chemical_class")),
        ("np_classifier.pathway",         row["np_classifier_pathway"],    plugin_doc.get("coconut", {}).get("np_classifier", {}).get("pathway")),
        ("collections (raw)",             row["collections"],              plugin_doc.get("coconut", {}).get("collections")),
        ("synonyms count",                len([s for s in row["synonyms"].split("|") if s]),
                                          len(plugin_doc.get("coconut", {}).get("synonyms", []))),
    ]
    for label, src_val, plug_val in checks:
        match = "✓" if src_val == plug_val else "✗"
        print(f"  {match}  {label:<35}  src={repr(src_val)!s:<30}  plugin={repr(plug_val)}")

    # ── REST API vs plugin field diff ─────────────────────────────────────
    if api_doc:
        print("\n" + "─" * 70)
        print("  REST API  vs  PLUGIN  (field coverage)")
        print("─" * 70)

        plugin_coconut = plugin_doc.get("coconut", {})

        # Compare molecule-level fields
        print("\n  Molecule base fields:")
        api_base_fields = {k: v for k, v in api_doc.items() if k != "properties"}
        for field, api_val in sorted(api_base_fields.items()):
            # Find equivalent in plugin
            equiv_map = {
                "identifier": plugin_coconut.get("coconut_id"),
                "standard_inchi_key": plugin_doc.get("_id"),
                "standard_inchi": plugin_coconut.get("inchi"),
                "canonical_smiles": plugin_coconut.get("smiles"),
                "iupac_name": plugin_coconut.get("iupac_name"),
                "name": plugin_coconut.get("name"),
                "annotation_level": plugin_coconut.get("properties", {}).get("annotation_level"),
                "murko_framework": plugin_coconut.get("murcko_framework"),
            }
            plug_val = equiv_map.get(field, "—")
            match = "✓" if api_val == plug_val else ("·" if field in API_ONLY_FIELDS else "?")
            api_only = "  [API-only]" if field in API_ONLY_FIELDS else ""
            print(f"    {match}  {field:<35}  api={repr(api_val)!s:<25}  plugin={repr(plug_val)}{api_only}")

        print("\n  Properties (via include):")
        for field, api_val in sorted((api_doc.get("properties") or {}).items()):
            plug_val = plugin_coconut.get("properties", {}).get(field)
            match = "✓" if api_val == plug_val else "✗"
            print(f"    {match}  {field:<35}  api={repr(api_val)!s:<25}  plugin={repr(plug_val)}")

    # ── BioThings server vs parser ────────────────────────────────────────
    if server_doc:
        print("\n" + "─" * 70)
        print("  BIOTHINGS SERVER  vs  PARSER  (field diff)")
        print("─" * 70)
        parser_keys = flatten_keys(plugin_doc)
        server_keys = flatten_keys(server_doc)
        only_parser = parser_keys - server_keys
        only_server = server_keys - parser_keys
        if only_parser:
            print(f"  In parser only:  {sorted(only_parser)}")
        if only_server:
            print(f"  In server only:  {sorted(only_server)}")
        if not only_parser and not only_server:
            print("  Field sets match exactly.")

    # ── Full documents ────────────────────────────────────────────────────
    print("\n" + "─" * 70)
    print("  FULL PLUGIN DOCUMENT  (parser.py output)")
    print("─" * 70)
    print(json.dumps(plugin_doc, indent=2))

    if api_doc:
        print("\n" + "─" * 70)
        print("  FULL REST API DOCUMENT  (POST /api/molecules/search)")
        print("─" * 70)
        print(json.dumps(api_doc, indent=2))

    if server_doc:
        print("\n" + "─" * 70)
        print("  FULL BIOTHINGS SERVER DOCUMENT  (localhost:9999)")
        print("─" * 70)
        print(json.dumps(server_doc, indent=2))


if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else "CNP0116685.1"
    compare(query)
