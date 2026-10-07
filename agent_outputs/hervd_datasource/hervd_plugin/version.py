"""Determine the current release/version string for HervD Atlas."""


def get_release(self):
    import requests

    url = "https://download.cncb.ac.cn/hervd/Disease%20Information.txt"
    try:
        resp = requests.head(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        last_modified = resp.headers.get("Last-Modified")
        if last_modified:
            # e.g. "Sat, 30 Sep 2023 08:37:12 GMT" -> "20230930"
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(last_modified)
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: hardcoded date matching the last observed Last-Modified
    # header on the canonical download files (2023-09-30), consistent with
    # the NAR 2024 Database Issue paper's submission/publication window.
    return "20230930"
