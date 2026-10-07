def get_release(self):
    import re

    import requests

    url = "https://ttd.idrblab.cn/files/download/P1-01-TTD_target_download.txt"
    try:
        resp = requests.get(url, headers={"Range": "bytes=0-500"}, timeout=30)
        text = resp.text
        m = re.search(r"Version\s+([0-9.]+)\s*\((\d{4})\.(\d{2})\.(\d{2})\)", text)
        if m:
            version, year, month, day = m.group(1), m.group(2), m.group(3), m.group(4)
            return f"{version}_{year}{month}{day}"
    except Exception:
        pass
    return None
