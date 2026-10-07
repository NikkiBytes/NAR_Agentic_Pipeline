"""
Custom dumper for HervD Atlas.

Why a custom dumper: the association-level data (which HERV is linked to
which disease) is only exposed through the site's `herv_term` and
`herv_element` endpoints, and both REQUIRE an HTTP POST rather than the GET
that biothings.hub.dataload.dumper.HTTPDumper issues. Both endpoints return
the FULL table in a single call (21,049 and 741 rows respectively; no
pagination, no query parameters, no auth) -- functionally a bulk dump, just
served over POST instead of GET. The `Disease Information.txt` reference
file (used for ontology cross-reference lookups) IS a normal GET-able static
file and is fetched the standard way.

This subclasses HTTPDumper (see manifest-schema.md "API-only source --
custom dumper.py" pattern) and overrides `download()` to route the two JSON
endpoints through `self.client.post(...)` while keeping GET for the plain
text file.
"""

from biothings.hub.dataload.dumper import HTTPDumper, DumperException

POST_URLS = {
    "https://ngdc.cncb.ac.cn/hervd/herv_term",
    "https://ngdc.cncb.ac.cn/hervd/herv_element",
}


class HervdDumper(HTTPDumper):

    SRC_NAME = "hervd"
    SRC_ROOT_FOLDER = None  # set by Hub config

    SRC_URLS = [
        "https://download.cncb.ac.cn/hervd/Disease%20Information.txt",
        "https://ngdc.cncb.ac.cn/hervd/herv_term",
        "https://ngdc.cncb.ac.cn/hervd/herv_element",
    ]

    UA_HEADERS = {"User-Agent": "Mozilla/5.0"}

    def download(self, remoteurl, localfile, headers=None):
        headers = dict(headers or {})
        headers.update(self.UA_HEADERS)
        self.prepare_local_folders(localfile)

        if remoteurl in POST_URLS:
            response = self.client.post(remoteurl, headers=headers, timeout=60)
            local_name = {
                "https://ngdc.cncb.ac.cn/hervd/herv_term": "herv_term.json",
                "https://ngdc.cncb.ac.cn/hervd/herv_element": "herv_element.json",
            }[remoteurl]
            import os

            localfile = os.path.join(os.path.dirname(localfile), local_name)
        else:
            response = self.client.get(remoteurl, headers=headers, timeout=60)
            import os

            localfile = os.path.join(os.path.dirname(localfile), "Disease Information.txt")

        if response.status_code != 200:
            raise DumperException(
                f"Error while downloading '{remoteurl}' "
                f"(status: {response.status_code}, reason: {response.reason})"
            )

        with open(localfile, "wb") as fh:
            fh.write(response.content)
        return response
