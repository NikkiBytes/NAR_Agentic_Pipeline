"""
Custom dumper for TarBase v9.0.

Why a custom dumper: the full aggregated miRNA-gene interaction table is
only exposed through the site's `get_all_interactions/` internal API route,
which REQUIRES an HTTP POST with a JSON body (an empty object `{}` returns
the entire unfiltered table) rather than the GET that
biothings.hub.dataload.dumper.HTTPDumper issues by default. This is a
single-call, non-paginated response (1,847,088 rows, ~115 MB CSV) --
functionally a bulk dump, just served over POST.

This subclasses HTTPDumper (see manifest-schema.md "API-only source --
custom dumper.py" pattern) and overrides `download()` to route the POST
request and save the response body as a local CSV file.
"""

import os

from biothings.hub.dataload.dumper import HTTPDumper, DumperException

POST_URL = "https://dianalab.e-ce.uth.gr/tarbasev9/api/get_all_interactions/"


class TarbaseDumper(HTTPDumper):

    SRC_NAME = "tarbase"
    SRC_ROOT_FOLDER = None  # set by Hub config

    SRC_URLS = [POST_URL]

    UA_HEADERS = {"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"}

    def download(self, remoteurl, localfile, headers=None):
        headers = dict(headers or {})
        headers.update(self.UA_HEADERS)
        self.prepare_local_folders(localfile)

        response = self.client.post(remoteurl, headers=headers, json={}, timeout=300)
        localfile = os.path.join(os.path.dirname(localfile), "tarbase_all_interactions.csv")

        if response.status_code != 200:
            raise DumperException(
                f"Error while downloading '{remoteurl}' "
                f"(status: {response.status_code}, reason: {response.reason})"
            )

        with open(localfile, "wb") as fh:
            fh.write(response.content)
        return response
