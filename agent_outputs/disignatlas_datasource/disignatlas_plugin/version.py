import logging
import re

logger = logging.getLogger(__name__)

DOWNLOAD_PAGE = "http://www.inbirg.com/disignatlas/download"
README_URL = "http://www.inbirg.com/disignatlas/download/readme"
# Observed on the download page's release table on 2026-08-13: the first
# RELEASED ON date on the page belongs to the dataset-info CSV row
# ("Disease Information of All DiSignAtlas Datasets", RELEASED ON 2023-09-01).
# The DEG GMT row on the same page is dated 2023-10-07, and README.txt
# separately states "DiSignAtlas 1.0 download  Last modified: October 7, 2023"
# for the overall download package. Regex picks the first date on the page
# (CSV row) as the release string; fall back to that same date if scraping fails.
FALLBACK_RELEASE = "20230901"


class ReleaseNotFoundError(Exception):
    pass


def get_release(self):
    """Return the current release date of DiSignAtlas as YYYYMMDD.

    DiSignAtlas has no version/info API. The download page renders a
    release table (RELEASED ON column, e.g. "2023-10-07") and README.txt
    restates the same date ("Last modified: October 7, 2023"). Try the
    download page first, then README.txt, then fall back to the last
    confirmed release string.
    """
    import requests

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        resp = requests.get(DOWNLOAD_PAGE, headers=headers, timeout=30)
        resp.raise_for_status()
        match = re.search(r"(\d{4}-\d{2}-\d{2})", resp.text)
        if match:
            return match.group(1).replace("-", "")
    except Exception as e:
        logger.warning("Could not determine release from download page: %s", e)

    try:
        resp = requests.get(README_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        match = re.search(
            r"Last modified:\s*([A-Za-z]+)\s+(\d{1,2}),\s*(\d{4})", resp.text
        )
        if match:
            month_name, day, year = match.groups()
            try:
                import datetime

                dt = datetime.datetime.strptime(
                    f"{month_name} {day} {year}", "%B %d %Y"
                )
                return dt.strftime("%Y%m%d")
            except ValueError:
                pass
    except Exception as e:
        logger.warning("Could not determine release from README.txt: %s", e)

    logger.warning(
        "Falling back to last confirmed DiSignAtlas release string: %s",
        FALLBACK_RELEASE,
    )
    return FALLBACK_RELEASE
