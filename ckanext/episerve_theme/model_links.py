"""Browser links for recorded, immutable GHCR image references."""

import re
from urllib.parse import urlencode


_IMAGE = re.compile(r'(ghcr\.io/[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+)@(sha256:[0-9a-f]{64})')


def image_links(reference):
    """Build package and exact-manifest links for a pinned GHCR image.

    Args:
        reference: Recorded image repository followed by its SHA-256 digest.

    Returns:
        Image identity and browser URLs, or None for unpinned or invalid values.
    """
    match = _IMAGE.fullmatch(reference) if isinstance(reference, str) else None
    if not match:
        return None
    return {'image': match[1], 'reference': reference, 'digest': match[2],
            'image_url': f'https://{match[1]}',
            'digest_url': 'https://explore.ggcr.dev/?' + urlencode({'image': reference})}
