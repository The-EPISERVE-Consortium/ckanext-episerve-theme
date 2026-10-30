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
    download, run = view["steps"]          # oldest first
    assert (run["label"], run["time"], run["url"]) == ("model run: baseline-nullmodel", "2026-10-19", "/dataset/q1792420591934")
    # a file links to its object's page at the version shown (preview and download are there), else its current page
    assert run["inputs"] == [{"label": "GrippeWeb.parquet", "version": "93ee770f", "external": False,
                              "qid": "Q3274128860531", "note": "", "url": f"/dataset/q3274128860531?version={V}"}]
    assert run["outputs"] == [{"label": "predictions.tsv", "version": "", "external": False,
                               "qid": "Q1792420591934", "note": "", "url": "/dataset/q1792420591934"}]
    # a download that names the version it produced links that version
    versioned = {**RESULT, "events": [_event("dataset-downloader/grippeweb", "Q3274128860531", "dataset", "2026-10-19T00:00:00Z",
                                             [], [_ds("Q3274128860531/GrippeWeb.parquet", V)])]}
    wrote = l.view(versioned, DOIP)["steps"][0]["outputs"][0]
    assert wrote["version"] == "93ee770f" and wrote["url"] == f"/dataset/q3274128860531?version={V}"
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


def test_diagram_joins_the_same_file_and_marks_the_current_object():
    diagram = l.view(RESULT, DOIP)["mermaid"].splitlines()
    assert diagram[0] == "flowchart LR"
    # GrippeWeb.parquet is one box: written by the download, read by the run
    assert "d0 --> j0" in diagram and "j1 --> d0" in diagram
    assert any(line.startswith('d0["GrippeWeb.parquet<br/>@93ee770f"]') for line in diagram)   # QID: tooltip
    assert "class j0 current" in diagram and "class d1 current" in diagram


def test_labels_cannot_break_the_diagram():
    result = {"object": "Q1", "events": [_event('dataset-downloader/x"]-->evil', "Q1792420591934", "dataset", "",
                                                [], [_ds('Q1792420591934/a"<b>.csv')])]}
    diagram = l.view(result, DOIP)["mermaid"]
    assert '"]-->evil' not in diagram and "<b>" not in diagram


def test_no_events_means_no_diagram():
    assert l.view({"object": "Q1", "kind": "model", "events": []}, DOIP) == {
        "object": "Q1", "kind": "model", "mermaid": "", "links": {}, "steps": [], "unresolved": [],
        "truncated": []}


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
                     "version": "cccccccc", "external": False, "qid": "", "note": ""}
    assert raw["label"] == "data-raw: incidence/x.tsv" and raw["url"] is None
    assert "lakefs://" not in str(view)


def test_a_file_in_a_folder_shows_its_name_and_links_its_path():
    result = {"object": "Q1792267434533", "events": [_event(
        "model-runner/model__prediction__generic__chronos2-small", "Q1792267434533", "run", "2026-10-17T12:00:00Z",
        [], [_ds("Q1792267434533/output/predictions.tsv")])]}
    out = l.view(result, DOIP)["steps"][0]["outputs"][0]
    assert out["label"] == "predictions.tsv"
    assert out["url"] == "/dataset/q1792267434533"


def test_boxes_link_like_the_table_and_show_the_qid_as_tooltip():
    links = l.view(RESULT, DOIP)["links"]
    assert links["j0"] == {"url": "/dataset/q1792420591934", "title": "Q1792420591934"}
    assert links["d0"] == {"url": f"/dataset/q3274128860531?version={V}", "title": "Q3274128860531"}
    assert links["d2"]["url"].startswith("https://raw.githubusercontent.com/") and links["d2"]["title"] == "RKI (GitHub)"


def test_long_names_wrap_instead_of_being_cut():
    result = {"object": "Q1", "events": [_event("dataset-downloader/x", "Q1679286399912", "dataset", "", [],
                                                [_ds("Q1679286399912/COVID-19-Faelle_7-Tage-Inzidenz_Bundeslaender.parquet")])]}
    box = next(line for line in l.view(result, DOIP)["mermaid"].splitlines() if line.startswith("d0["))
    assert "…" not in box and "Bundeslaender.parquet" in box and box.count("<br/>") >= 1


def test_source_shows_when_it_last_changed():
    event = _event("dataset-downloader/x", "Q1679286399912", "dataset", "2026-10-16T23:00:13Z",
                   [{"namespace": "https://api.open-meteo.com", "name": "v1/forecast"}], [])
    event["run"]["facets"]["episerve"]["source_changed_at"] = "2026-10-16T08:00:00Z"
    view = l.view({"object": "Q1", "events": [event]}, DOIP)
    assert view["steps"][0]["inputs"][0]["note"] == "changed 2026-10-16"
    assert "Open-Meteo<br/>changed 2026-10-16" in view["mermaid"]
