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


V = "93ee770fc2315d43" + "0" * 48


def test_steps_link_to_the_files_and_carry_versions():
    view = l.view(RESULT, DOIP)
    run, download = view["steps"]
    assert (run["label"], run["time"], run["url"]) == ("model run: baseline-nullmodel", "2026-10-19", "/dataset/q1792420591934")
    # read: the file at the version the run read; wrote: the file as it is
    assert run["inputs"] == [{"label": "GrippeWeb.parquet", "version": "93ee770f", "external": False, "restricted": False,
                              "url": f"{DOIP}/doip/retrieve/Q3274128860531/GrippeWeb.parquet?version={V}"}]
    assert run["outputs"] == [{"label": "predictions.tsv", "version": "", "external": False, "restricted": False,
                               "url": f"{DOIP}/doip/retrieve/Q1792420591934/predictions.tsv"}]
    # a download that names the version it produced links that version
    versioned = {**RESULT, "events": [_event("dataset-downloader/grippeweb", "Q3274128860531", "dataset", "2026-10-19T00:00:00Z",
                                             [], [_ds("Q3274128860531/GrippeWeb.parquet", V)])]}
    wrote = l.view(versioned, DOIP)["steps"][0]["outputs"][0]
    assert wrote["version"] == "93ee770f" and wrote["url"].endswith(f"GrippeWeb.parquet?version={V}")
    assert download["label"] == "download: grippeweb"
    source = download["inputs"][0]
    assert source["external"] and source["label"] == "RKI (GitHub)"
    assert source["url"].startswith("https://raw.githubusercontent.com/robert-koch-institut/")


def test_source_names():
    assert l.source_name("https://raw.githubusercontent.com/robert-koch-institut/X/main/x.tsv") == "RKI (GitHub)"
    assert l.source_name("https://raw.githubusercontent.com/someone/X/main/x.tsv") == "someone (GitHub)"
    assert l.source_name("https://api.open-meteo.com/v1/forecast?latitude=52") == "Open-Meteo"
    assert l.source_name("https://xmart-api-public.who.int/FLUMART/VIW_FNT") == "WHO"
    assert l.source_name("https://example.org/data.csv") == "example.org"


def test_restricted_files_are_linked_only_when_signed():
    anonymous = l.view(RESULT, DOIP, restricted={"Q3274128860531"})
    read = anonymous["steps"][0]["inputs"][0]
    assert read["url"] is None and read["restricted"] and read["version"] == "93ee770f"
    assert anonymous["steps"][0]["outputs"][0]["url"].endswith("/Q1792420591934/predictions.tsv")   # open
    signed = l.view(RESULT, DOIP, restricted={"Q3274128860531"}, sign=lambda u: u + "?exp=1&sig=s")
    assert signed["steps"][0]["inputs"][0]["url"] == (
        f"{DOIP}/doip/retrieve/Q3274128860531/GrippeWeb.parquet?exp=1&sig=s&version={V}")


def test_platform_qids():
    assert l.platform_qids(RESULT, DOIP) == {"Q3274128860531", "Q1792420591934"}


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


def test_files_inside_the_cluster_are_never_linked():
    old = "c" * 64
    result = {"object": "Q1792267434533", "events": [_event(
        "model-runner/model__prediction__generic__chronos2-small", "Q1792267434533", "run", "2026-10-17T12:00:00Z",
        [{"namespace": "lakefs://benchmarks", "name": "2/input.parquet",
          "facets": {"version": {"datasetVersion": old}}},
         {"namespace": "lakefs://data-raw", "name": "incidence/x.tsv"}],
        [_ds("Q1792267434533/predictions.tsv")])]}
    view = l.view(result, DOIP, api_url="https://api.example/")
    bench, raw = view["steps"][0]["inputs"]
    assert bench == {"label": "benchmark 2: input.parquet", "url": "https://api.example/ui/benchmarks/2",
                     "version": "cccccccc", "external": False, "restricted": False}
    assert raw["label"] == "data-raw: incidence/x.tsv" and raw["url"] is None
    assert "lakefs://" not in str(view)
