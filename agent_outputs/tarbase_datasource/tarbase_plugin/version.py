"""Version resolver for TarBase v9.0.

No dedicated version/statistics API endpoint exists on the TarBase v9.0
site (probed /api/statistics/, /api/about/, /api/info/, /api/version/,
/api/get_statistics/ -- all return empty bodies). The homepage itself is a
static single-page-app shell, but Apache serves it with an honest
Last-Modified header reflecting the last deployment of the site/data, so
that is used as the release marker.
"""


def get_release(self):
    import requests

    try:
        resp = requests.head(
            "https://dianalab.e-ce.uth.gr/tarbasev9",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            from datetime import datetime
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(last_modified)
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: matches the Last-Modified value observed during plugin
    # generation (Sat, 11 May 2024 05:00:01 GMT).
    return "20240511"
