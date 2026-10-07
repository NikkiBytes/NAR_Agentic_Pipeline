def get_release(self):
    """Return a version string for the current PancanQTLv2.0 release.

    PancanQTLv2.0 does not publish a version/build endpoint, a "last
    updated" date on its homepage, or a dated release archive. The most
    reliable dynamic signal is the Last-Modified HTTP header on one of its
    static bulk download files, which reflects when the underlying data
    files were last (re)generated on the server.
    """
    import datetime

    import requests

    probe_url = (
        "https://hanlaboratory.com/static/PancanQTLv2/Download/"
        "Fine-mapping/BRCA.cis.susie.txt.gz"
    )
    try:
        resp = requests.head(
            probe_url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            allow_redirects=True,
        )
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            # e.g. "Wed, 27 Sep 2023 20:37:56 GMT" -> "20230927"
            dt = datetime.datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: paper acceptance date (2023-10-06), used only if the
    # Last-Modified header is ever removed or the request fails.
    return "20231006"
