def get_release(self):
    """Return a version string for the current INTEDE bulk-download release.

    INTEDE's bulk .txt files embed their own version/date in the header
    comment block, e.g.:
        Title - Complete EC Tree of DMEs
        Version 1.8.1 (2020.08.15)

    Strategy:
    1. Fetch the small DME cross-matching file and regex out "Version X.Y.Z (YYYY.MM.DD)".
    2. Fall back to the HTTP Last-Modified header on the MICBIO CSV file.
    3. Fall back to a hardcoded date matching the file header seen at generation time.
    """
    import re
    import requests

    xref_url = (
        "https://intede.idrblab.net/sites/default/files/INTEDE_Download/"
        "P2-04-1-INTEDE_DME_Cross_Matching_ID.txt"
    )
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(xref_url, headers=headers, timeout=30, stream=True)
        resp.raise_for_status()
        # Only need the first ~1KB to find the header block.
        chunk = next(resp.iter_content(chunk_size=1024)).decode("utf-8", errors="ignore")
        m = re.search(r"Version\s+([\d.]+)\s*\((\d{4})\.(\d{2})\.(\d{2})\)", chunk)
        if m:
            version, year, month, day = m.groups()
            return f"{version}_{year}{month}{day}"
    except Exception:
        pass

    try:
        csv_url = (
            "https://intede.idrblab.net/sites/default/files/INTEDE_Download/"
            "P1-01-1-INTEDE_MICBIO_DME_Interaction.csv"
        )
        resp = requests.head(csv_url, headers=headers, timeout=30, allow_redirects=True)
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            from email.utils import parsedate_to_datetime
            dt = parsedate_to_datetime(last_modified)
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    return "1.8.1_20200815"
