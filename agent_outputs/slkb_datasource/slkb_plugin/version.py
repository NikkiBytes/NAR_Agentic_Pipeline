def get_release(self):
    """Return a release string for the SLKB Figshare deposit.

    SLKB's bulk data export (SQL_Dumps.zip) is hosted on Figshare
    (article 22902839, DOI 10.6084/m9.figshare.22902839). Figshare's public
    API exposes the deposit's version number and last-modified timestamp,
    which together uniquely identify the current release of the archive.
    """
    import requests

    try:
        resp = requests.get(
            "https://api.figshare.com/v2/articles/22902839",
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        version = data.get("version")
        modified = data.get("modified_date")
        if modified:
            # e.g. "2023-08-22T16:39:38Z" -> "20230822"
            date_part = modified.split("T")[0].replace("-", "")
            if version is not None:
                return f"v{version}_{date_part}"
            return date_part
        if version is not None:
            return f"v{version}"
    except Exception:
        pass

    # Fallback: hardcoded snapshot of the only release observed at
    # plugin-generation time (Figshare article version 1, modified
    # 2023-08-22), in case the Figshare API is temporarily unreachable.
    return "v1_20230822"
