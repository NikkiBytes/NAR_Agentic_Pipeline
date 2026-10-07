def get_release(self):
    """
    Determine the release date of the scTWAS Atlas eQTL data by checking
    the Last-Modified header of the bulk download file.
    Falls back to the scTWAS homepage for any visible date.
    """
    import requests

    url = "https://ngdc.cncb.ac.cn/sctwas/static/file/Allstudies_sig_eQTL.txt"
    try:
        resp = requests.head(url, timeout=30, allow_redirects=True)
        resp.raise_for_status()
        last_modified = resp.headers.get("Last-Modified", "")
        if last_modified:
            # Parse "Thu, 02 Jan 2025 09:40:45 GMT" → "20250102"
            from email.utils import parsedate
            import time
            parsed = parsedate(last_modified)
            if parsed:
                t = time.mktime(parsed)
                from datetime import datetime
                dt = datetime.utcfromtimestamp(t)
                return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: check homepage for any visible date text
    try:
        resp = requests.get("https://ngdc.cncb.ac.cn/sctwas/", timeout=30)
        import re
        # Look for a 4-digit year pattern
        matches = re.findall(r"(202[0-9])", resp.text)
        if matches:
            return max(matches) + "00"  # year-only fallback
    except Exception:
        pass

    return None
