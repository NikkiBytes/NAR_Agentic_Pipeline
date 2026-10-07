def get_release(self):
    """Return a version string for circRNADisease based on the bulk file's
    HTTP Last-Modified header (the site does not publish a numeric release
    tag or a version/changelog endpoint)."""
    import requests

    url = "https://cgga.org.cn/circRNADisease/download/circRNADisease_V3_circrna_details.txt"
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True,
                            headers={"User-Agent": "Mozilla/5.0"})
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            from datetime import datetime
            dt = datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: today's date, so a release string is always produced
    from datetime import date
    return date.today().strftime("%Y%m%d")
