"""Validated navigation links for recorded dataset, file, and model identifiers."""

import json
import re
from urllib.parse import urlencode, urlsplit

from ckanext.episerve_theme.versions import valid_commit

_QID = re.compile(r'Q\d+', re.IGNORECASE)


def links(key, raw, run_header=None):
    """Build link descriptors while leaving malformed metadata as plain text.

    Args:
        key: Catalog extra field name.
        raw: Original field value, usually a JSON list or a model QID.
        run_header: Prepared run provenance with recorded source/model versions.

    Returns:
        Validated link descriptors, or an empty list for unsupported values.
    """
    if key not in ('input_dataset_qids', 'input_sources', 'model_qid'):
        return []
    if key == 'model_qid':
        values = [raw]
    else:
        try:
            values = json.loads(raw) if isinstance(raw, str) else raw
        except (ValueError, TypeError):
            return []
    if not isinstance(values, list) or not values or not all(isinstance(item, str) for item in values):
        return []
    header = run_header or {}
    result = []
    for value in values:
        if key == 'input_sources':
            try:
                parts = urlsplit(value)
                valid = (parts.scheme in ('http', 'https') and parts.hostname
                         and not parts.username and not parts.password
                         and not re.search(r'[\s\x00-\x1f\x7f]', value))
                parts.port  # Reject malformed ports before creating a link.
            except ValueError:
                valid = False
            if not valid:
                return []
            result.append({'label': value, 'url': value, 'file': True})
            continue
        if not _QID.fullmatch(value):
            return []
        qid = value.upper()
        if key == 'model_qid':
            versions = [header.get('model_version') if header.get('model_qid') == qid else None]
        else:
            versions = [source.get('version') for source in header.get('sources', []) if source.get('qid') == qid] or [None]
        for version in dict.fromkeys(versions):
            commit = valid_commit(version)
            url = '/dataset/' + qid.lower()
            if commit:
                url += '?' + urlencode({'version': commit})
            result.append({'label': qid, 'url': url, 'file': False})
    return result
