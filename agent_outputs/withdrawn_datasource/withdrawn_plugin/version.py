def get_release(self):
    """Return a release string for Withdrawn 2.0.

    Withdrawn 2.0 (https://bioinformatics.charite.de/withdrawn_3/) does not
    expose a version/info API or a "last updated" date on its homepage.
    The most reliable freshness signal is the HTTP Last-Modified header on
    the bulk CSV download itself, so use that (formatted YYYYMMDD). Fall
    back to a hardcoded date (the value observed at generation time) if the
    HEAD request fails or the header is missing.
    """
    import requests
    from datetime import datetime

    url = "https://bioinformatics.charite.de/withdrawn_3/downloads/withdrawns.csv"
    fallback = "20231016"

    try:
        resp = requests.head(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            dt = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    return fallback
