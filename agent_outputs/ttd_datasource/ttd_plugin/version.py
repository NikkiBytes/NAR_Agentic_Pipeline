def get_release(self):
    import re
    import requests
    # Extract version string from the P1-02 file header, which contains:
    # "Version 10.1.01 (2024.01.10)"
    url = "https://ttd.idrblab.cn/files/download/P1-02-TTD_drug_download.txt"
    try:
        resp = requests.get(url, stream=True, timeout=30,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        for line in resp.iter_lines(decode_unicode=True):
            if not line:
                continue
            m = re.search(r"Version\s+([\d.]+)\s+\((\d{4}\.\d{2}\.\d{2})\)", line)
            if m:
                version, date = m.group(1), m.group(2).replace(".", "")
                return f"{version}_{date}"
            # Stop after header section (data rows start with drug IDs like D00...)
            if line[:1] == "D" and len(line) > 5:
                break
    except Exception:
        pass
    return None
