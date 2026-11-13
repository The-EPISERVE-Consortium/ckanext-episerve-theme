"""Check recorded versions and safe rendering of Additional Info navigation."""

import json

import pytest

from ckanext.episerve_theme.extra_links import links
from tests.test_run_snapshot import render_info


def test_dataset_links_preserve_each_recorded_version():
    """Link distinct source snapshots without inventing pins for other datasets."""
    first, second = 'a' * 64, 'b' * 64
    header = {'sources': [{'qid': 'Q12', 'version': first}, {'qid': 'Q12', 'version': second}]}
    result = links('input_dataset_qids', '["Q12", "Q34"]', header)
    assert [item['url'] for item in result] == [
        '/dataset/q12?version=' + first, '/dataset/q12?version=' + second, '/dataset/q34']


def test_model_links_only_use_matching_catalog_versions():
    """A source Git SHA is never substituted for a lakeFS model-object version."""
    header = {'model_qid': 'Q12', 'model_version': 'a' * 64}
    assert links('model_qid', 'Q12', header)[0]['url'] == '/dataset/q12?version=' + 'a' * 64
    assert links('model_qid', 'Q34', header)[0]['url'] == '/dataset/q34'
    assert links('model_qid', 'Q12', {**header, 'model_version': 'a' * 40})[0]['url'] == '/dataset/q12'


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'data:text/html,hello',
    'https://user:password@example.org/file', 'https://example.org:bad/file',
    'https://example.org/\nfile', 'https://[invalid/file', '//example.org/file'])
def test_invalid_input_file_links_remain_plain_text(url):
    """Do not create active links from malformed or executable URL values.

    Args:
        url: Recorded value that must not become an anchor target.
    """
    assert links('input_sources', json.dumps([url])) == []


def test_additional_info_renders_links_and_escapes_file_labels():
    """Render identifiers and full versioned file URLs as safe anchors."""
    url = 'https://doip.example/doip/retrieve/Q12/input.parquet?version=' + 'a' * 64
    html = render_info(run_header={'sources': [{'qid': 'Q12', 'version': 'a' * 64}]},
                       extras=[{'key': 'input_dataset_qids', 'value': '["Q12"]'},
                              {'key': 'input_sources', 'value': json.dumps([url])},
                              {'key': 'model_qid', 'value': 'Q34'}])
    assert 'href="/dataset/q12?version=' + 'a' * 64 + '"' in html
    assert 'href="/dataset/q34"' in html
    assert f'href="{url}"' in html
    assert 'rel="noopener noreferrer"' in html
    hostile = 'https://example.org/<script>alert(1)</script>'
    html = render_info(extras=[{'key': 'input_sources', 'value': json.dumps([hostile])}])
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_legacy_and_malformed_fields_keep_original_values():
    """Leave unknown fields, invalid lists and non-QID model identifiers alone."""
    assert links('status', 'success') == []
    assert links('input_dataset_qids', '["Q12", "not-a-qid"]') == []
    assert links('input_sources', 'not-json') == []
    assert links('model_qid', 'javascript:alert(1)') == []
    html = render_info(extras=[{'key': 'input_dataset_qids', 'value': 'legacy format'}])
    assert 'legacy format' in html
