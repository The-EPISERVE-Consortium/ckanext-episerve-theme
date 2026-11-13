"""Check recorded model snapshots and their Additional Info presentation."""

from pathlib import Path
from types import SimpleNamespace

import jinja2
import pytest

from ckanext.episerve_theme import labels
from ckanext.episerve_theme.run_header import model_snapshot

MODEL = 'model__prediction__generic__timesfm'
IMAGE = f'ghcr.io/the-episerve-consortium/{MODEL}'
DIGEST = 'sha256:' + 'a' * 64
SOURCE = 'b' * 40
REPOSITORY = f'https://github.com/The-EPISERVE-Consortium/{MODEL}'


def recorded_fdo(source=SOURCE):
    """Create a run FDO matching the model runner's emitted provenance.

    Args:
        source: Source revision label recorded by the runner.

    Returns:
        FDO with an immutable image reference and snapshot properties.
    """
    return {'provenance': {'prov:wasAssociatedWith': {
        '@id': f'{IMAGE}@{DIGEST}', 'schema:softwareVersion': DIGEST,
        'schema:additionalProperty': [
            {'schema:name': name, 'schema:value': value}
            for name, value in [('model_tag', 'latest'), ('model_digest', DIGEST),
                                ('model_source_revision', source)]
        ],
    }}}


def render_info(snapshot=None, source_url='', extras=None):
    """Render the production Additional Info snippet with minimal CKAN helpers.

    Args:
        snapshot: Prepared recorded image snapshot.
        source_url: Catalog Source link.
        extras: Catalog extras to render.

    Returns:
        Autoescaped Additional Info table HTML.
    """
    template = (Path(__file__).parents[1] / 'ckanext/episerve_theme/templates/package/snippets/additional_info.html').read_text()
    template = template.replace('{% ckan_extends %}', '')
    # Date snippets are unrelated to these rows; render no dates in this fixture.
    template = template.replace("{% snippet 'snippets/local_friendly_datetime.html', datetime_obj=pkg_dict.metadata_modified %}", '')
    template = template.replace("{% snippet 'snippets/local_friendly_datetime.html', datetime_obj=pkg_dict.metadata_created %}", '')
    template = template.replace("{% snippet 'snippets/local_friendly_datetime.html', datetime_obj=when %}", '')
    helpers = SimpleNamespace(
        is_url=lambda value: value.startswith('https://'), check_access=lambda *args: False,
        get_pkg_dict_extra=lambda pkg, key: None,
        sorted_extras=lambda items: [(item['key'], item['value']) for item in items],
        episerve_is_card_extra=lambda key: False, episerve_as_datetime=lambda value: None,
        episerve_extra_label=labels.label, episerve_extra_value=labels.value,
    )
    env = jinja2.Environment(autoescape=True)
    return env.from_string(template).render(
        pkg_dict={'id': 'run', 'url': source_url, 'extras': extras or []},
        model_snapshot=snapshot, h=helpers, _=lambda text: text,
    )


def test_snapshot_uses_the_recorded_container_and_source_versions():
    """Build distinct immutable identities for image execution and GitHub code."""
    snapshot = model_snapshot(recorded_fdo(), MODEL)
    assert snapshot['reference'] == f'{IMAGE}@{DIGEST}'
    assert snapshot['digest'] == DIGEST
    assert snapshot['source_revision'] == SOURCE
    assert snapshot['tag'] == 'latest'
    assert snapshot['source_url'] == f'{REPOSITORY}/tree/{SOURCE}'
    assert DIGEST not in snapshot['source_url']


def test_additional_info_displays_full_values_and_pins_source_links():
    """Show the digest and Git SHA in the info table and preserve the model tag."""
    html = render_info(model_snapshot(recorded_fdo(), MODEL), REPOSITORY, extras=[
        {'key': 'docker_tag', 'value': 'legacy-sync-value'},
        {'key': 'status', 'value': 'success'},
    ])
    assert DIGEST in html
    assert SOURCE in html
    assert 'latest' in html
    assert 'Image digest' in html and 'Source Git commit' in html
    assert html.count(f'href="{REPOSITORY}/tree/{SOURCE}"') == 2
    assert f'href="{REPOSITORY}"' not in html
    assert 'legacy-sync-value' not in html
    assert 'success' in html


@pytest.mark.parametrize('source', ['unavailable', 'latest', '<script>alert(1)</script>', None])
def test_missing_source_keeps_digest_without_inventing_a_pinned_link(source):
    """Do not infer a commit from a moving tag or malformed provenance.

    Args:
        source: Absent or invalid recorded source revision.
    """
    snapshot = model_snapshot(recorded_fdo(source), MODEL)
    html = render_info(snapshot)
    assert DIGEST in html
    assert 'Unavailable' in html
    assert '/tree/' not in html
    assert '<script>' not in html


def test_legacy_runs_keep_existing_additional_info():
    """An older run's catalog fields remain visible without fabricated versions."""
    assert model_snapshot(None, MODEL) is None
    assert model_snapshot({'provenance': {'prov:wasAssociatedWith': {'@id': IMAGE + ':latest'}}}, MODEL) is None
    html = render_info(extras=[{'key': 'docker_tag', 'value': 'v1'}])
    assert 'v1' in html
    assert 'Image digest' not in html


def test_unrelated_source_links_are_preserved():
    """Never replace a dataset's unrelated Source URL with a model repository."""
    url = 'https://example.org/research'
    html = render_info(model_snapshot(recorded_fdo(), MODEL), url)
    assert f'href="{url}"' in html
    assert f'href="{REPOSITORY}/tree/{SOURCE}"' in html


def test_repository_mismatch_does_not_guess_a_github_link():
    """Only link GitHub when the recorded EPISERVE image matches the model."""
    snapshot = model_snapshot(recorded_fdo(), 'some-other-model')
    assert snapshot['source_url'] is None
    assert SOURCE in render_info(snapshot)


def test_conflicting_provenance_is_not_displayed_as_a_verified_snapshot():
    """Do not pair a source SHA with conflicting container identities."""
    fdo = recorded_fdo()
    fdo['provenance']['prov:wasAssociatedWith']['schema:additionalProperty'].append(
        {'schema:name': 'model_digest', 'schema:value': 'sha256:' + 'c' * 64})
    assert model_snapshot(fdo, MODEL) is None


def test_recorded_tags_are_escaped():
    """Render recorded strings as text rather than executable HTML."""
    fdo = recorded_fdo()
    fdo['provenance']['prov:wasAssociatedWith']['schema:additionalProperty'][0]['schema:value'] = '<script>alert(1)</script>'
    html = render_info(model_snapshot(fdo, MODEL))
    assert '<script>' not in html
    assert '&lt;script&gt;' in html


def test_image_and_digest_links_use_distinct_registry_destinations():
    """The image opens its package and the digest opens the exact manifest."""
    from urllib.parse import parse_qs, urlsplit

    snapshot = model_snapshot(recorded_fdo(), MODEL)
    assert snapshot['image_url'] == 'https://' + IMAGE
    target = urlsplit(snapshot['digest_url'])
    assert target.scheme == 'https' and target.netloc == 'explore.ggcr.dev'
    assert parse_qs(target.query) == {'image': [IMAGE + '@' + DIGEST]}
    html = render_info(snapshot)
    assert f'href="{snapshot["image_url"]}"' in html
    assert f'href="{snapshot["digest_url"]}"' in html
    assert 'rel="noopener noreferrer"' in html


def test_digest_link_does_not_follow_a_moving_tag():
    """An older digest stays the link target even if its requested tag changes."""
    from urllib.parse import parse_qs, urlsplit

    record = recorded_fdo()
    record['provenance']['prov:wasAssociatedWith']['schema:additionalProperty'][0]['schema:value'] = 'v2'
    snapshot = model_snapshot(record, MODEL)
    assert parse_qs(urlsplit(snapshot['digest_url']).query)['image'] == [IMAGE + '@' + DIGEST]
    assert 'v2' not in snapshot['digest_url']
