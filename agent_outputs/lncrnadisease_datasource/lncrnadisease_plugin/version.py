def get_release(self):
    """Return a release string for LncRNADisease v3.0.

    LncRNADisease has no versioned API or release endpoint. The most reliable
    signal for "current release" is the HTTP Last-Modified header on the bulk
    download files themselves -- take the most recent Last-Modified across
    both files actually ingested (website_simple_data.csv, website_alldata.tsv)
    and format it as YYYYMMDD. Falls back to a hardcoded date observed during
    plugin generation if both HEAD requests fail.
    """
    import requests
    from datetime import datetime

    urls = [
        "http://www.rnanut.net/lncrnadisease/static/download/website_simple_data.csv",
        "http://www.rnanut.net/lncrnadisease/static/download/website_alldata.tsv",
    ]

    latest = None
    headers = {"User-Agent": "Mozilla/5.0"}
    for url in urls:
        try:
            resp = requests.head(url, headers=headers, timeout=30, allow_redirects=True)
            lm = resp.headers.get("Last-Modified")
            if not lm:
                continue
            dt = datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z")
            if latest is None or dt > latest:
                latest = dt
        except Exception:
            continue

    if latest:
        return latest.strftime("%Y%m%d")

    # Fallback: most recent Last-Modified observed during plugin generation
    # (website_simple_data.csv, 2024-03-25)
    return "20240325"
