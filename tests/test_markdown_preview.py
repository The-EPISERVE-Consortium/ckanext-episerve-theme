"""Verify raw Markdown preview URL selection and safe template serialization."""

import json
from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest


def render(format, url):
    """Render the real override against a minimal existing text-view template.

    Args:
        format: Resource format spelling.
        url: Signed and/or pinned URL returned by the resource helper.

    Returns:
        Rendered script block without requiring CKAN.
    """
    source = (Path(__file__).parents[1] / 'ckanext/episerve_theme/templates/text_view.html').read_text()
    source = source.replace('{% ckan_extends %}', '{% extends "core.html" %}')
    env = jinja2.Environment(autoescape=True, loader=jinja2.DictLoader({
        'view.html': source,
        'core.html': '{% block scripts %}<script>var resource_url="original";</script>{% endblock %}',
    }))
    return env.get_template('view.html').render(
        resource={'format': format}, package={'name': 'q1'},
        h=SimpleNamespace(episerve_file_url=lambda resource, package: url))


@pytest.mark.parametrize('format', ['MD', 'md', 'MARKDOWN'])
def test_markdown_preview_preserves_signed_pinned_file_url(format):
    """Use the resource helper rather than losing the recorded version or access.

    Args:
        format: Supported Markdown format label.
    """
    url = 'https://doip.example/doip/retrieve/Q1/notes.md?exp=123&sig=abc&version=' + 'a' * 64
    html = render(format, url)
    value = html.rsplit('resource_url = ', 1)[1].split(';', 1)[0]
    assert json.loads(value) == url
    assert 'var resource_url="original";' in html


def test_other_text_views_keep_their_existing_behavior_and_urls_are_escaped():
    """Leave JSON/log previews alone and keep URL text outside executable HTML."""
    assert 'resource_url = ' not in render('JSON', 'https://example.org/new')
    assert 'resource_url = ' not in render('LOG', 'https://example.org/new')
    html = render('MD', 'https://example.org/</script><script>alert(1)</script>')
    assert '</script><script>alert(1)' not in html
    assert '\\u003c/script\\u003e' in html
