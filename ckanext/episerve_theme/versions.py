"""A dataset page at one version: ``/dataset/<qid>?version=<commit>``.

The CKAN entry describes the newest version. For an older version the page takes the metadata from the FDO at
that lakeFS commit (read through the DOIP server) and points previews and downloads at that commit. The version
must be one of the object's commits (``/doip/versions/<QID>``); anything else is "not found". Nothing here imports
CKAN, so it can be tested on its own.
"""

import re
from typing import Callable
from urllib.parse import urlsplit

COMMIT = re.compile(r"[0-9a-f]{64}")
_QID_NAME = re.compile(r"[Qq]\d{6,}")


def valid_commit(value) -> str | None:
    """The value when it is a full lakeFS commit ID, else None."""
    value = (value or "").strip().lower() if isinstance(value, str) else ""
    return value if COMMIT.fullmatch(value) else None


def with_version(url: str, commit: str | None, doip_base: str) -> str:
    """A DOIP file URL at ``commit`` (other URLs, and no commit, unchanged). Sign first: signing skips URLs
    that already have a query."""
    if not url or not commit or not url.startswith(f"{doip_base.rstrip('/')}/doip/retrieve/"):
        return url
    return f"{url}{'&' if '?' in url else '?'}version={commit}"


def fdo_url(pkg: dict, commit: str, doip_base: str) -> str:
    """The FDO record of the entry at ``commit`` (the CKAN resource ``fdo.json`` holds the newest one)."""
    return f"{doip_base.rstrip('/')}/doip/retrieve/{(pkg.get('name') or '').upper()}?version={commit}"


def is_fdo_resource(res: dict) -> bool:
    return (res.get("name") or "") == "fdo.json" or urlsplit(res.get("url") or "").path.endswith("/fdo.json")


def _extras(pkg: dict) -> dict:
    return {e.get("key"): e.get("value") for e in pkg.get("extras") or [] if isinstance(e, dict)}


def versioned_pkg(pkg: dict, fdo: dict) -> dict:
    """The entry as it was at that version: name, description, dates and source from the FDO.

    Only a dataset's text comes from its FDO; benchmark data and model runs keep the entry's text (it holds
    links the sync writes, and their FDO does not change).
    """
    profile = fdo.get("profile") or {}
    kernel = fdo.get("kernel") or {}
    provenance = fdo.get("provenance") or {}
    extras = _extras(pkg)
    out = dict(pkg)
    if extras.get("dataset_type") == "raw-data":
        out["title"] = profile.get("display_name") or profile.get("name") or pkg.get("title")
        out["notes"] = profile.get("description") or pkg.get("notes")
        out["url"] = profile.get("url") or pkg.get("url")
    modified = kernel.get("modified") or provenance.get("prov:generatedAtTime")
    if modified:
        out["metadata_modified"] = modified.rstrip("Z")
    replace = {"modified": modified, "source_changed_at": provenance.get("source_changed_at")}
    out["extras"] = [
        {**e, "value": replace[e.get("key")]} if replace.get(e.get("key")) else e
        for e in pkg.get("extras") or []
    ]
    return out


def version_view(pkg: dict, requested, fetch_versions: Callable[[str], list | None],
                 fetch_fdo: Callable[[str, str], dict | None]) -> dict | None:
    """What the page shows for ``?version=``: None without one, else a dict with ``found``.

    Found: ``commit``, ``short``, ``date`` (of that version), ``latest`` (is it the newest), ``pkg`` (the entry at
    that version). Not found (not a commit of this object, or its FDO cannot be read): ``requested`` only.
    """
    if requested is None:
        return None
    not_found = {"found": False, "requested": str(requested)[:80]}
    name = pkg.get("name") or ""
    commit = valid_commit(requested)
    if not commit or not _QID_NAME.fullmatch(name):
        return not_found
    versions = fetch_versions(name.upper()) or []
    entry = next((v for v in versions if v.get("commit_id") == commit), None)
    if entry is None:
        return not_found
    fdo = fetch_fdo(name.upper(), commit)
    if not fdo:
        return not_found
    return {
        "found": True,
        "commit": commit,
        "short": commit[:8],
        "date": (entry.get("timestamp_iso8601") or "")[:16].replace("T", " "),
        "latest": versions[0].get("commit_id") == commit,
        "pkg": versioned_pkg(pkg, fdo),
    }
