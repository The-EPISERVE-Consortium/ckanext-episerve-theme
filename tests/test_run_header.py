"""Check generic run metadata, provenance retention and safe fallbacks."""
from ckanext.episerve_theme.run_header import header


def run(**extras):
    """Build a catalog run fixture.

    Args:
        **extras: Structured run metadata.

    Returns:
        Catalog package carrying the supplied extras.
    """
    return {'groups': [{'name': 'type-model-run'}],
            'extras': [{'key': key, 'value': value} for key, value in extras.items()]}


def test_generic_run_title_and_all_sources():
    """Format a run without model-specific rules and retain multiple inputs."""
    result = header(run(model='model__prediction__generic__chronos2-small', model_qid='Q123',
                        run_timestamp='2026-10-17T14:05:57Z', input_dataset_qids='["Q11", "Q22", "Q11"]'))
    assert result['title'] == 'Chronos2-small model run · 17 Oct 2026, 14:05'
    assert result['model_qid'] == 'Q123'
    assert [source['qid'] for source in result['sources']] == ['Q11', 'Q22']


def test_preserve_sql_and_custom_notes():
    """Keep recorded SQL as inert text and retain additional description content."""
    pkg = run(model='model__anything__test', data_transformation_sql='["fallback"]')
    pkg['notes'] = 'This item represents a run of model [test](/dataset/q1).\n\nRecorded data transformation SQL:\n\n```sql\nSELECT "value" FROM df WHERE label = \'<script>\'\n```\n\nResearcher note.'
    result = header(pkg)
    assert result['notes'] == 'Researcher note.'
    assert result['sql'] == ['SELECT "value" FROM df WHERE label = \'<script>\'']


def test_missing_and_legacy_metadata():
    """Retain readable fallback content when dates or optional fields are missing."""
    assert header({'extras': []}) is None
    assert header({'extras': [{'key': 'model', 'value': 'test'}]}) is None
    pkg = run(model='test', model_qid='javascript:alert(1)', run_timestamp='unparsed', data_transformation_sql='SELECT 1')
    assert header(pkg)['title'] == 'Test model run · unparsed'
    assert header(pkg)['model_qid'] is None
    assert header(pkg)['sql'] == ['SELECT 1']
    pkg = run(model='test')
    pkg['title'] = 'Model-run with model: test [20261017-1405]'
    assert header(pkg)['title'] == 'Test model run · 17 Oct 2026, 14:05'
