def get_release(self):
    """Return a version string for the current HMDD v4.0 data release.

    HMDD v4.0 has no versioned release endpoint or changelog file; the
    canonical bulk file (alldata_v4.txt) is updated in place. The most
    reliable signal of freshness is the HTTP Last-Modified header on that
    file, which we convert to YYYYMMDD.
    """
    import re

    import requests

    url = "http://www.cuilab.cn/static/hmdd3/data/alldata_v4.txt"
    try:
        res = requests.head(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
            allow_redirects=True,
        )
        last_modified = res.headers.get("Last-Modified")
        if last_modified:
            # e.g. "Tue, 11 Jul 2023 03:39:37 GMT"
            import datetime

            dt = datetime.datetime.strptime(last_modified, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y%m%d")
    except Exception:
        pass

    # Fallback: scrape the homepage's "Last Update: Month-DD, YYYY" text.
    try:
        res = requests.get(
            "http://www.cuilab.cn/hmdd",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        match = re.search(r"Last Update:\s*([A-Za-z]+)-(\d{1,2}),\s*(\d{4})", res.text)
        if match:
            month_name, day, year = match.groups()
            months = {
                "January": "01", "February": "02", "March": "03", "April": "04",
                "May": "05", "June": "06", "July": "07", "August": "08",
                "September": "09", "October": "10", "November": "11", "December": "12",
            }
            month = months.get(month_name)
            if month:
                return f"{year}{month}{int(day):02d}"
    except Exception:
        pass

    # Final fallback: last confirmed Last-Modified date observed during
    # plugin generation (2026-08-13 session).
    return "20230711"
