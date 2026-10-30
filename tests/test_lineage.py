"""The Lineage tab's view of the API's upstream lineage (event shapes as returned by the live API)."""

from ckanext.episerve_theme import lineage as l

DOIP = "https://doip.episerve.zib.de"


def _ds(name, version=None):
    entry = {"namespace": DOIP, "name": name}
    if version:
        entry["facets"] = {"version": {"datasetVersion": version}}
    return entry


def _event(job, qid, kind, when, inputs, outputs):
    return {"eventTime": when, "job": {"name": job}, "run": {"facets": {"episerve": {"qid": qid, "kind": kind}}},
            "inputs": inputs, "outputs": outputs}


RESULT = {
    "object": "Q1792420591934", "kind": "run", "unresolved": [], "truncated": [],
    "events": [
        _event("model-runner/model__prediction__grippeweb__baseline-nullmodel", "Q1792420591934", "run",
               "2026-10-19T14:36:56Z", [_ds("Q3274128860531/GrippeWeb.parquet", "93ee770fc2315d43" + "0" * 48)],
               [_ds("Q1792420591934/predictions.tsv")]),
        _event("dataset-downloader/grippeweb", "Q3274128860531", "dataset", "2026-10-30T00:00:16Z",
               [{"namespace": "https://raw.githubusercontent.com", "name": "robert-koch-institut/GrippeWeb/main/GrippeWeb.tsv",
                 "facets": {"dataSource": {"uri": "https://raw.githubusercontent.com/robert-koch-institut/GrippeWeb/main/GrippeWeb.tsv"}}}],
               [_ds("Q3274128860531/GrippeWeb.parquet")]),
    ],
}


def test_tab_only_for_objects_with_upstream():
    assert l.qid_for({"name": "q1792420591934", "groups": [{"name": "type-model-run"}]}) == "Q1792420591934"
    assert l.qid_for({"name": "q7611536028271", "groups": [{"name": "type-model"}]}) is None
    assert l.qid_for({"name": "some-dataset", "groups": []}) is None
    assert l.valid_qid("Q1792420591934") and not l.valid_qid("Q1/../x") and not l.valid_qid("")


def test_steps_link_to_ckan_pages_and_carry_versions():
    view = l.view(RESULT, DOIP)
    run, download = view["steps"]
    assert (run["label"], run["time"], run["url"]) == ("model run: baseline-nullmodel", "2026-10-19", "/dataset/q1792420591934")
    assert run["inputs"] == [{"label": "GrippeWeb.parquet", "url": "/dataset/q3274128860531", "version": "93ee770f",
                              "external": False}]
    assert run["outputs"][0]["label"] == "predictions.tsv"
    assert download["label"] == "download: grippeweb"
    source = download["inputs"][0]
    assert source["external"] and source["url"].startswith("https://raw.githubusercontent.com/")
    assert source["label"] == "raw.githubusercontent.com › GrippeWeb.tsv"


def test_diagram_joins_the_same_file_and_marks_the_current_object():
    diagram = l.view(RESULT, DOIP)["mermaid"].splitlines()
    assert diagram[0] == "flowchart LR"
    # GrippeWeb.parquet is one box: written by the download, read by the run
    assert "d0 --> j0" in diagram and "j1 --> d0" in diagram
    assert any(line.startswith('d0["GrippeWeb.parquet<br/>Q3274128860531<br/>@93ee770f"]') for line in diagram)
    assert "class j0 current" in diagram and "class d1 current" in diagram


def test_labels_cannot_break_the_diagram():
    result = {"object": "Q1", "events": [_event('dataset-downloader/x"]-->evil', "Q1792420591934", "dataset", "",
                                                [], [_ds('Q1792420591934/a"<b>.csv')])]}
    diagram = l.view(result, DOIP)["mermaid"]
    assert '"]-->evil' not in diagram and "<b>" not in diagram


def test_no_events_means_no_diagram():
    assert l.view({"object": "Q1", "kind": "model", "events": []}, DOIP) == {
        "object": "Q1", "kind": "model", "mermaid": "", "steps": [], "unresolved": [], "truncated": []}
