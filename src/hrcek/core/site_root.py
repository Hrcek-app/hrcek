"""Files served at the root of the site, such as /robots.txt.

They live in `site_root/` beside this module. WhiteNoise serves them
from memory before a request reaches any view; see
docs/dev/deployment.md.
"""

from __future__ import annotations

from pathlib import Path
from wsgiref.headers import Headers

DIRECTORY = Path(__file__).resolve().parent / "site_root"

# Crawlers fetch robots.txt about once a day; WhiteNoise's own default
# for files without a hash in the name is a minute.
MAX_AGE = 24 * 60 * 60


def add_headers(headers: Headers, path: str, url: str) -> None:
    """Let browsers and proxies keep a root file for a day."""
    if Path(path).parent == DIRECTORY:
        headers["Cache-Control"] = f"public, max-age={MAX_AGE}"
