"""Signed, expiring links to restricted DOIP components (no CKAN imports).

Must stay compatible with ``doip_shared.signing`` in the DOIP server: ``sig`` is the
hex HMAC-SHA256 of ``"<QID>\\n<component>\\n<exp>"`` under the shared secret.
"""

import hashlib
import hmac
import time
from urllib.parse import unquote


def sign(secret, qid, component, exp):
    message = f"{qid.upper()}\n{component}\n{int(exp)}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def sign_doip_url(url, retrieve_base, secret, ttl=3600, now=None):
    """Return ``url`` with ``exp`` and ``sig`` appended if it is a DOIP component URL.

    Args:
        url: Resource URL, e.g. ``https://doip.example/doip/retrieve/Q1/data.parquet``.
        retrieve_base: ``<DOIP public URL>/doip/retrieve/`` prefix identifying DOIP URLs.
        secret: Shared signing secret; when empty the URL is returned unchanged.
        ttl: Lifetime of the link in seconds.
        now: Current time override for tests.

    Returns:
        The signed URL, or ``url`` unchanged when it is not a DOIP component URL
        (other host, no component, already has a query string) or no secret is set.
    """
    if not url or not secret or not url.startswith(retrieve_base) or "?" in url or "#" in url:
        return url
    qid, _, component = url[len(retrieve_base):].partition("/")
    if not qid or not component:
        return url
    exp = int((time.time() if now is None else now) + ttl)
    # The server verifies the percent-decoded component, as it sees it after routing.
    return f"{url}?exp={exp}&sig={sign(secret, qid, unquote(component), exp)}"
