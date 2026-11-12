"""Render the real run page with minimal CKAN snippet and helper fixtures."""

from pathlib import Path
from types import SimpleNamespace

import jinja2
from jinja2 import nodes
from jinja2.ext import Extension
from markupsafe import Markup
import pytest

TEMPLATES = Path(__file__).parents[1] / 'ckanext/episerve_theme/templates'


class Snippets(Extension):
    """Implement the two CKAN tags needed to render the unmodified page."""

    tags = {'snippet', 'asset', 'link_for'}

    def parse(self, parser):
        """Parse a CKAN snippet call and its keyword arguments.

        Args:
            parser: Jinja parser positioned on a custom tag.

        Returns:
            Output node rendering a fixture asset or the actual snippet template.
        """
        token = next(parser.stream)
        filename = parser.parse_expression()
        keywords = []
        while parser.stream.skip_if('comma'):
            key = parser.stream.expect('name').value
            parser.stream.expect('assign')
            keywords.append(nodes.Keyword(key, parser.parse_expression()))
        call = self.call_method('render', [nodes.ContextReference(), nodes.Const(token.value), filename], keywords)
        return nodes.Output([call]).set_lineno(token.lineno)

    def render(self, context, tag, filename, **kwargs):
        """Render actual forecast snippets while stubbing unrelated tab content.

        Args:
            context: Parent template context.
            tag: Asset or snippet tag.
            filename: Requested template or bundle.
            **kwargs: Snippet variables.

        Returns:
            Safe HTML produced by the template or asset fixture.
        """
        if tag == 'asset':
            return Markup('<script src="/static/forecast_preview.js"></script>')
        if filename != 'package/snippets/forecast_preview.html':
            return ''
        return Markup(self.environment.get_template(filename).render({**context.get_all(), **kwargs}))


def render_page(entry_type='model-run', restricted=False, authenticated=False):
    """Render package/read.html using the real forecast tab markup.

    Args:
        entry_type: Catalog entry kind.
        restricted: Whether anonymous file access is hidden.
        authenticated: Whether the fixture visitor is signed in.

    Returns:
        Complete page HTML suitable for unit and browser validation.
    """
    loader = jinja2.ChoiceLoader([
        jinja2.DictLoader({'package/read_base.html': '{% block primary %}{% endblock %}'}),
        jinja2.FileSystemLoader(TEMPLATES),
    ])
    env = jinja2.Environment(loader=loader, extensions=[Snippets], autoescape=True)
    pkg = {'id': 'id', 'name': 'q1793997474911', 'type': 'dataset', 'state': 'active', 'notes': '',
           'resources': [], 'groups': [{'name': 'type-model-run'}] if entry_type == 'group-only-model-run' else [], 'extras': [{'key': 'dataset_type', 'value': entry_type},
                                      {'key': 'access', 'value': 'restricted' if restricted else 'open'}]}
    helpers = SimpleNamespace(
        episerve_version=lambda pkg: None,
        get_pkg_dict_extra=lambda pkg, key: next((e['value'] for e in pkg['extras'] if e['key'] == key), None),
        episerve_model_card=lambda extras: None, episerve_lineage_qid=lambda pkg: None,
        check_access=lambda *args: False, dataset_display_name=lambda pkg: 'Model run fixture',
        episerve_with_created=lambda pkg: pkg,
    )
    return env.get_template('package/read.html').render(pkg=pkg, h=helpers, _=lambda text: text,
                                                        current_user=SimpleNamespace(is_authenticated=authenticated))


@pytest.mark.parametrize('entry_type,restricted,authenticated,visible', [
    ('model-run', False, False, True), ('group-only-model-run', False, False, True), ('model-run', True, False, False),
    ('model-run', True, True, True), ('raw-data', False, False, False), ('model', False, False, False),
])
def test_forecast_tab_is_scoped_to_permitted_model_run_pages(entry_type, restricted, authenticated, visible):
    """Keep other entry kinds and anonymous restricted runs unchanged.

    Args:
        entry_type: Entry kind under test.
        restricted: Whether source file tabs require authentication.
        authenticated: Fixture login state.
        visible: Expected presence of the forecast tab.
    """
    html = render_page(entry_type, restricted, authenticated)
    assert ('Input &amp; Forecast' in html) is visible
    assert ('id="tab-forecast"' in html) is visible
    if visible:
        assert 'style="display:none"' in html
        assert 'data-qid="q1793997474911"' in html
        assert 'epiForecast()' in html
        assert html.index("epiTab(this,'tab-forecast')") < html.index("epiTab(this,'tab-resources')")
        assert "epi-ds-tab active\" type=\"button\" onclick=\"epiTab(this,'tab-forecast')" in html
        assert '<div class="epi-pane" id="tab-forecast">' in html
        assert '<div class="epi-pane" id="tab-resources" style="display:none">' in html
