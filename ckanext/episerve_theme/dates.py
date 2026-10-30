"""The "Created" date of an entry: when the object was made, not when its CKAN entry was (re)created.

The sync flow stores the FDO's own creation time as the extra ``created`` (a model's first registration, a model
run's start). CKAN's ``metadata_created`` is the time the entry was created and changes when it is recreated.
Nothing here imports CKAN.
"""

import re

_ISO = re.compile(r"(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2}:\d{2})(\.\d+)?(Z|[+-]00:?00)?")


def created_for(pkg: dict) -> str | None:
    """The extra ``created`` as CKAN's datetime form (``YYYY-MM-DDTHH:MM:SS``, UTC), or None if absent or unreadable."""
    extras = {e.get("key"): e.get("value") for e in pkg.get("extras") or [] if isinstance(e, dict)}
    match = _ISO.fullmatch((extras.get("created") or "").strip())
    return f"{match.group(1)}T{match.group(2)}" if match else None


def with_created(pkg: dict) -> dict:
    """The entry with ``metadata_created`` replaced by the object's own creation time when the sync stored one."""
    created = created_for(pkg)
    return {**pkg, "metadata_created": created} if created else pkg
