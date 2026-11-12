"""Exercise the CKAN proxy without requiring a CKAN installation."""

import importlib.util
from io import BytesIO
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest


class Response:
    """Small response stand-in retaining status, JSON and HTTP headers."""

    def __init__(self, body, status=200, content_type=None, headers=None):
        """Capture proxy output.

        Args:
            body: JSON response body.
            status: HTTP status.
            content_type: Declared MIME type.
            headers: HTTP response headers.
        """
        self.body, self.status_code, self.headers = body, status, headers or {}


@pytest.fixture
def proxy(monkeypatch):
    """Import the real plugin with minimal CKAN and Flask surface fixtures.

    Args:
        monkeypatch: Fixture restoring imported framework stubs after each test.

    Returns:
        Plugin module and mutable catalog/request fixture state.
    """
    state = {'package': {'groups': [{'name': 'type-model-run'}]}, 'query': {}, 'calls': []}
    ckan = ModuleType('ckan')
    plugins = ModuleType('ckan.plugins')
    toolkit = ModuleType('ckan.plugins.toolkit')
    toolkit.current_user = SimpleNamespace(name=None)
    toolkit.request = SimpleNamespace(args=state['query'])
    toolkit.ObjectNotFound = type('ObjectNotFound', (Exception,), {})
    toolkit.NotAuthorized = type('NotAuthorized', (Exception,), {})

    def action(name):
        """Return the public package lookup fixture.

        Args:
            name: Requested CKAN action name.

        Returns:
            Catalog action callback.
        """
        def show(context, arguments):
            """Apply catalog access control before returning a run.

            Args:
                context: Visitor authorization context.
                arguments: Catalog entry identifier.

            Returns:
                Authorized package metadata.

            Raises:
                toolkit.NotAuthorized: Catalog denies the current visitor.
            """
            if state.get('denied'):
                raise toolkit.NotAuthorized()
            return state['package']
        return show

    toolkit.get_action = action
    plugins.SingletonPlugin = object
    plugins.implements = lambda *args: None
    plugins.IConfigurer = plugins.IBlueprint = plugins.ITemplateHelpers = object
    plugins.toolkit = toolkit
    ckan.plugins = plugins
    flask = ModuleType('flask')
    flask.Response, flask.Blueprint, flask.g = Response, object, SimpleNamespace()
    for name, module in [('ckan', ckan), ('ckan.plugins', plugins), ('ckan.plugins.toolkit', toolkit), ('flask', flask)]:
        monkeypatch.setitem(sys.modules, name, module)
    spec = importlib.util.spec_from_file_location('forecast_plugin_fixture', Path(__file__).parents[1] / 'ckanext/episerve_theme/plugin.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def open_url(url, timeout):
        """Return an API payload while recording the requested URL.

        Args:
            url: Trusted API URL produced by the proxy.
            timeout: Bounded upstream request timeout.

        Returns:
            Context-managed JSON byte stream.
        """
        state['calls'].append(url)
        return BytesIO(b'{"predictions": []}')

    monkeypatch.setattr(module.urllib.request, 'urlopen', open_url)
    return module, state


def test_proxy_preserves_version_and_disables_http_caching(proxy):
    """Send the requested exact run version through the same-origin proxy.

    Args:
        proxy: Actual plugin with framework fixtures.
    """
    module, state = proxy
    state['query']['version'] = 'a' * 64
    response = module.forecast_preview_view('q1793997474911')
    assert response.status_code == 200
    assert state['calls'][0].endswith('/model-runs/Q1793997474911/forecast-preview?version=' + 'a' * 64)
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('case,status', [('denied', 404), ('invalid-version', 400), ('wrong-kind', 404)])
def test_proxy_refuses_unauthorized_or_invalid_requests_before_upstream(proxy, case, status):
    """Avoid triggering preview generation for denied or malformed requests.

    Args:
        proxy: Actual plugin with framework fixtures.
        case: Authorization or request defect.
        status: Expected HTTP status.
    """
    module, state = proxy
    if case == 'denied':
        state['denied'] = True
    elif case == 'wrong-kind':
        state['package']['groups'] = []
    else:
        state['query']['version'] = 'main'
    response = module.forecast_preview_view('q1793997474911')
    assert response.status_code == status and not state['calls']


def test_run_header_does_not_reveal_restricted_source_titles(proxy):
    """Leave source identifiers visible when the visitor cannot read their titles.

    Args:
        proxy: Plugin and catalog access fixtures.
    """
    module, state = proxy
    state['denied'] = True
    package = {'groups': [{'name': 'type-model-run'}], 'extras': [
        {'key': 'model', 'value': 'model__test'},
        {'key': 'input_dataset_qids', 'value': '["Q456"]'}]}
    result = module.episerve_run_header(package)
    assert result['sources'] == [{'qid': 'Q456', 'title': 'Q456', 'version': None}]


def test_run_header_pins_from_displayed_run_version(proxy, monkeypatch):
    """Resolve provenance from the selected run snapshot rather than its newest one.

    Args:
        proxy: Plugin and request fixtures.
        monkeypatch: Fixture replacing versioned metadata reads.
    """
    module, state = proxy
    selected, source_commit = 'a' * 64, 'b' * 64
    state['query']['version'] = selected
    state['package'] = {'title': 'Current source title'}
    package = {'name': 'q1234567', 'groups': [{'name': 'type-model-run'}], 'extras': [
        {'key': 'model', 'value': 'model__test'},
        {'key': 'input_dataset_qids', 'value': '["Q4567890"]'}]}
    calls = []

    def fetch(qid, commit):
        """Return snapshot metadata while recording exact version reads.

        Args:
            qid: Object identifier.
            commit: Requested immutable version.

        Returns:
            Recorded run provenance or source metadata.
        """
        calls.append((qid, commit))
        if qid == 'Q1234567':
            return {'provenance': {'prov:used': [{'@id': f'{module.DOIP_NAMESPACE}/doip/retrieve/Q4567890/file?version={source_commit}'}]}}
        return {'profile': {'display_name': 'Recorded source title'}}

    monkeypatch.setattr(module, '_fetch_fdo', fetch)
    result = module.episerve_run_header(package)
    assert calls == [('Q1234567', selected), ('Q4567890', source_commit)]
    assert result['sources'] == [{'qid': 'Q4567890', 'title': 'Recorded source title', 'version': source_commit}]
