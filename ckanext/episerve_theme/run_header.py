"""Present model-run metadata using the normal dataset header styling."""

from datetime import datetime
import json
import re

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
