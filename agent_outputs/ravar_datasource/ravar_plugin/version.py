def get_release(self):
    """Determine RAVAR's current release/version string.

    RAVAR (www.ravar.bio) exposes no version or "last updated" API endpoint
    (/api/about and /api/statistics both 404). The site's own static assets
    carry an HTTP Last-Modified date, which is the most reliable freshness
    signal available; fall back to a hardcoded date derived from the NAR
    2024 Database Issue publication (accepted 2023-09-28) if that request
    fails.
    """
    import requests

    try:
        resp = requests.head("http://www.ravar.bio", timeout=30)
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            # e.g. "Sat, 09 Sep 2023 14:08:29 GMT" -> "20230909"
            import datetime

            dt = datetime.datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    return "20230909"
