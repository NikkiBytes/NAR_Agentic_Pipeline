def get_release(self):
    import email.utils

    import requests

    # SORC has no versioned API or visible "last updated" banner on its homepage.
    # The most reliable version signal is the Last-Modified header on the dataset
    # manifest file itself, which changes whenever the site's data snapshot is refreshed.
    try:
        resp = requests.head(
            "https://bio-bigdata.hrbmu.edu.cn/SORC/0_files/innerpath/download_dataset.txt",
            timeout=30,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        lm = resp.headers.get("Last-Modified", "")
        if lm:
            dt = email.utils.parsedate_to_datetime(lm)
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: ETag often embeds a content-length/mtime-derived value that at
    # least changes when the file changes, even if not human-readable as a date.
    try:
        resp = requests.head(
            "https://bio-bigdata.hrbmu.edu.cn/SORC/0_files/innerpath/download_dataset.txt",
            timeout=30,
            verify=False,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        etag = resp.headers.get("ETag", "")
        if etag:
            return etag.strip('"').replace("W/", "").strip('"')
    except Exception:
        pass

    return None
