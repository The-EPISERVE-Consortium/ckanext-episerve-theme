"""A dataset page at one version (?version=<commit>), built from the FDO at that commit."""

from ckanext.episerve_theme import versions as v

DOIP = "https://doip.episerve.zib.de"
OLD, NEW = "a" * 64, "b" * 64
PKG = {
    "name": "q0522578154235", "title": "SARI (newest)", "notes": "newest text", "url": "https://src/new",
    "metadata_modified": "2026-10-30T03:00:07",
    "extras": [{"key": "dataset_type", "value": "raw-data"}, {"key": "modified", "value": "2026-10-30T00:00:07Z"},
               {"key": "source_changed_at", "value": "2026-10-30T00:00:07Z"}, {"key": "qid", "value": "Q0522578154235"}],
}
FDO_OLD = {"kernel": {"modified": "2026-10-17T00:00:05Z"},
           "profile": {"display_name": "SARI (old)", "description": "old text", "url": "https://src/old"},
           "provenance": {"source_changed_at": "2026-10-16T08:00:00Z"}}
VERSIONS = [{"commit_id": NEW, "timestamp_iso8601": "2026-10-30T00:00:07+00:00"},
            {"commit_id": OLD, "timestamp_iso8601": "2026-10-17T00:00:05+00:00"}]


def _view(requested, versions=VERSIONS, fdo=FDO_OLD, pkg=PKG):
    return v.version_view(pkg, requested, lambda q: versions, lambda q, c: fdo)


def test_no_version_parameter_means_the_normal_page():
    assert _view(None) is None


def test_an_older_version_shows_its_own_metadata():
    view = _view(OLD)
    assert view["found"] and view["short"] == "aaaaaaaa" and view["date"] == "2026-10-17 00:00" and not view["latest"]
    page = view["pkg"]
    assert (page["title"], page["notes"], page["url"]) == ("SARI (old)", "old text", "https://src/old")
    extras = {e["key"]: e["value"] for e in page["extras"]}
    assert extras["modified"] == "2026-10-17T00:00:05Z" and extras["source_changed_at"] == "2026-10-16T08:00:00Z"
    assert extras["qid"] == "Q0522578154235" and page["metadata_modified"] == "2026-10-17T00:00:05"
    assert PKG["title"] == "SARI (newest)"            # the entry itself is not changed


def test_the_newest_version_is_marked_latest():
    assert _view(NEW)["latest"]


def test_unknown_or_malformed_versions_are_not_found():
    assert _view("c" * 64) == {"found": False, "requested": "c" * 64}        # not a commit of this object
    assert _view("abc") == {"found": False, "requested": "abc"}               # not a full commit ID
    assert _view(OLD, fdo=None)["found"] is False                             # no FDO at that commit
    assert _view(OLD, versions=None)["found"] is False                        # versions not readable


def test_runs_and_benchmarks_keep_their_text():
    run = {**PKG, "extras": [{"key": "dataset_type", "value": "model-run"}]}
    page = _view(OLD, pkg=run)["pkg"]
    assert page["title"] == "SARI (newest)" and page["notes"] == "newest text"


def test_file_links_at_the_version():
    url = f"{DOIP}/doip/retrieve/Q1/x.parquet"
    assert v.with_version(url, OLD, DOIP) == f"{url}?version={OLD}"
    assert v.with_version(url + "?exp=1&sig=s", OLD, DOIP) == f"{url}?exp=1&sig=s&version={OLD}"
    assert v.with_version(url, None, DOIP) == url
    assert v.with_version("https://data.episerve.zib.de/x/fdo.json", OLD, DOIP).endswith("fdo.json")
    assert v.fdo_url(PKG, OLD, DOIP) == f"{DOIP}/doip/retrieve/Q0522578154235?version={OLD}"
    assert v.is_fdo_resource({"name": "fdo.json"}) and not v.is_fdo_resource({"name": "x.parquet", "url": url})
