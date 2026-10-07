"""
GENEasso version/release detection.

Primary strategy: fetch the download list API endpoint and extract the
most recent metadata signal.  The API returns JSON with a list of available
files — we use the response as a proxy for data currency.

Fallback: return today's date as YYYYMMDD.
"""

import warnings
from datetime import datetime


class MyVersioner:
    # Required by biothings-cli dataplugin validate
    SRC_NAME = "geneasso"

    def get_release(self):
        """Return a release string for the current GENEasso dataset."""
        try:
            import requests

            # Suppress InsecureRequestWarning — GENEasso SSL cert is expired
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = requests.get(
                    "https://www.geneasso.net/api/download/list",
                    timeout=30,
                    verify=False,
                )
            if r.status_code == 200:
                data = r.json()
                # API returns {"code":200,"data":[...]}
                # Use the paper publication date as the stable release string
                # since the API doesn't expose a last-updated timestamp.
                # Paper: NAR 2025, DOI: 10.1093/nar/gkaf1097
                # First online: 2025 (PMID 41166152)
                if data.get("code") == 200 and data.get("data"):
                    # Count files as a change signal — if count changes, bump version
                    n_files = len(data["data"])
                    # Current known count is 12 (including Script.download)
                    # Return a stable version string based on paper + file count
                    return f"20250101_{n_files}files"
        except Exception:
            pass

        # Fallback: today as YYYYMMDD
        return datetime.utcnow().strftime("%Y%m%d")
