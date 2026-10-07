def get_release(self):
    """Return MolBiC release string from HTTP Last-Modified header on the compound file."""
    import requests
    import re

    # Try HEAD on the compound file for Last-Modified
    try:
        r = requests.head(
            "https://molbic.idrblab.net/sites/files/full_data/1-3.%20Compound.txt",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            allow_redirects=True,
        )
        lm = r.headers.get("Last-Modified", "")
        if lm:
            from email.utils import parsedate
            from datetime import datetime
            parsed = parsedate(lm)
            if parsed:
                dt = datetime(*parsed[:6])
                return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: scrape molbic homepage for update date
    try:
        resp = requests.get(
            "https://molbic.idrblab.net/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        match = re.search(r"(\d{4}-\d{2}-\d{2})", resp.text)
        if match:
            return match.group(1).replace("-", "")
    except Exception:
        pass

    return "20241001"  # Last known update date from paper (NAR 2025, published Oct 2024)
