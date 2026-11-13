"""Present model-run metadata using the normal dataset header styling."""

from datetime import datetime
import json
import re
from urllib.parse import parse_qs, urlsplit

from ckanext.episerve_theme.versions import valid_commit
from ckanext.episerve_theme.model_links import image_links

_QID = re.compile(r"Q\d+", re.IGNORECASE)


def header(pkg):
    """Extract a readable run title and linked metadata without model-specific rules.

    Args:
        pkg: Catalog metadata for the displayed run version.

    Returns:
        Header fields, or None for other entries or missing model metadata.
    """
    extras = {item['key']: item.get('value') for item in pkg.get('extras', [])}
    groups = {item.get('name') for item in pkg.get('groups', [])}
    model = extras.get('model')
    if not model or not (extras.get('dataset_type') == 'model-run' or 'type-model-run' in groups):
        return None
    short = model.rsplit('__', 1)[-1]
    title = short[:1].upper() + short[1:] + ' model run'
    timestamp = extras.get('run_timestamp') or ''
    if not timestamp:
        match = re.search(r'\[(\d{8}-\d{4})\]$', pkg.get('title', ''))
        timestamp = match[1] if match else ''
    try:
        started = datetime.strptime(timestamp, '%Y%m%d-%H%M') if re.fullmatch(r'\d{8}-\d{4}', timestamp) else datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        title += ' · ' + started.strftime('%d %b %Y, %H:%M')
    except ValueError:
        if timestamp:
            title += ' · ' + timestamp
    sources = []
    for qid in _QID.findall(extras.get('input_dataset_qids') or ''):
        qid = qid.upper()
        if qid not in sources:
            sources.append(qid)
    notes = pkg.get('notes') or ''
    sql_blocks = re.findall(r'```sql\s*\n(.*?)\n```', notes, re.DOTALL)
    if not sql_blocks:
        raw = extras.get('data_transformation_sql') or ''
        try:
            sql_blocks = json.loads(raw)
        except (ValueError, TypeError):
            sql_blocks = [raw] if raw else []
        if isinstance(sql_blocks, str):
            sql_blocks = [sql_blocks]
        if not isinstance(sql_blocks, list):
            sql_blocks = []
    remaining = re.sub(r'^This item represents a run of model [^\n]*(?:\n\n|$)', '', notes)
    remaining = re.sub(r'Recorded data transformation SQL:\s*```sql\s*\n.*?\n```', '', remaining, flags=re.DOTALL).strip()
    model_qid = extras.get('model_qid') or ''
    return {'title': title, 'model': model,
            'model_qid': model_qid.upper() if _QID.fullmatch(model_qid) else None,
            'sources': [{'qid': qid, 'title': qid} for qid in sources],
            'sql': [sql for sql in sql_blocks if isinstance(sql, str) and sql.strip()],
            'notes': remaining}


def pin_links(header, fdo, doip_namespace):
    """Attach only immutable versions explicitly recorded in the run provenance.

    Args:
        header: Prepared run header metadata.
        fdo: The run's FDO at the displayed artifact version, or None.
        doip_namespace: Trusted public DOIP base URL.

    Returns:
        Header copy with separate source links for distinct recorded versions.
    """
    provenance = (fdo or {}).get('provenance') or {}
    used = provenance.get('prov:used') or []
    if isinstance(used, dict):
        used = [used]
    if not isinstance(used, list):
        used = []
    agent = provenance.get('prov:wasAssociatedWith') or {}
    entities = used + ([agent] if isinstance(agent, dict) else [])
    pins = {}
    prefix = doip_namespace.rstrip('/') + '/doip/retrieve/'
    for entity in entities:
        url = entity.get('@id', '') if isinstance(entity, dict) else ''
        if not isinstance(url, str) or not url.startswith(prefix):
            continue
        parts = urlsplit(url)
        qid = parts.path[len(urlsplit(prefix).path):].split('/', 1)[0].upper()
        values = parse_qs(parts.query, keep_blank_values=True).get('version', [])
        commit = valid_commit(values[0]) if len(values) == 1 else None
        if _QID.fullmatch(qid) and commit and commit not in pins.get(qid, []):
            pins.setdefault(qid, []).append(commit)
    sources = []
    for source in header['sources']:
        for commit in pins.get(source['qid'], [None]):
            sources.append({**source, 'version': commit})
    model_pins = pins.get(header.get('model_qid'), [])
    return {**header, 'sources': sources,
            'model_snapshot': model_snapshot(fdo, header['model']),
            'model_version': model_pins[0] if len(model_pins) == 1 else None,
            'model_version_note': ('version ambiguous' if len(model_pins) > 1 else
                                   ('version not recorded' if fdo else 'version unavailable'))}


def model_snapshot(fdo, model):
    """Extract the executed image snapshot from a run's recorded provenance.

    Args:
        fdo: Run FDO at the displayed lakeFS version, or None.
        model: Model repository name recorded in the catalog run.

    Returns:
        Snapshot fields for Additional Info, or None for legacy metadata.
        GitHub links use the source Git SHA, not the container digest. Source
        repositories are mapped only for matching EPISERVE model images. The
        digest links to Registry Explorer using the immutable image reference.
    """
    provenance = (fdo or {}).get('provenance') or {}
    agent = provenance.get('prov:wasAssociatedWith') or {}
    if not isinstance(agent, dict):
        return None
    links = image_links(agent.get('@id'))
    if not links:
        return None
    properties = agent.get('schema:additionalProperty') or []
    if isinstance(properties, dict):
        properties = [properties]
    values = {}
    if isinstance(properties, list):
        for prop in properties:
            if not isinstance(prop, dict):
                continue
            name, value = prop.get('schema:name'), prop.get('schema:value')
            if isinstance(name, str) and isinstance(value, str):
                # A conflicting field must not be used to claim an exact snapshot.
                values[name] = value if name not in values or values[name] == value else None
    digest = links['digest']
    if 'model_digest' in values and values['model_digest'] != digest:
        return None
    source = values.get('model_source_revision')
    if not isinstance(source, str) or not re.fullmatch(r'[0-9a-fA-F]{40}|[0-9a-fA-F]{64}', source):
        source = None
    repository_url = None
    owner, repository = links['image'].removeprefix('ghcr.io/').split('/', 1)
    if owner.lower() == 'the-episerve-consortium' and repository.lower() == model.lower():
        repository_url = f'https://github.com/The-EPISERVE-Consortium/{repository}'
    return {**links,
            'tag': values.get('model_tag'), 'source_revision': source,
            'repository_url': repository_url,
            'source_url': f'{repository_url}/tree/{source}' if repository_url and source else None}
