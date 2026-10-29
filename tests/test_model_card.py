import json

from ckanext.episerve_theme import model_card as mc

PARAMETERS = {
    "type": "object",
    "required": ["history_length"],
    "additionalProperties": False,
    "properties": {
        "history_length": {"type": "integer", "minimum": 3, "unit": "steps", "description": "rows of history"},
        "prediction_length": {"type": "integer", "minimum": 1, "maximum": 512},
        "prediction_offset": {"type": "integer", "minimum": 0, "default": 0},
        "method": {"type": "string", "enum": ["mean", "median"], "default": "mean"},
        "alpha": {"type": ["number", "null"], "exclusiveMinimum": 0, "exclusiveMaximum": 1},
    },
    "rules": ["history_length + prediction_offset <= rows"],
}


def _extras(**sections):
    extras = [{"key": "model_qid", "value": "Q1"}]
    for name, value in sections.items():
        extras.append({"key": f"model_{name}", "value": value if isinstance(value, str) else json.dumps(value)})
    return extras


def test_no_card_extras_means_no_tab():
    assert mc.model_card([{"key": "model_qid", "value": "Q1"}]) is None
    assert mc.model_card([]) is None


def test_parameter_rows():
    rows = {r["name"]: r for r in mc.model_card(_extras(parameters=PARAMETERS))["parameters"]}
    assert list(rows) == ["history_length", "prediction_length", "prediction_offset", "method", "alpha"]
    assert rows["history_length"] == {
        "name": "history_length", "required": True, "type": "integer (steps)", "default": "",
        "range": "≥ 3", "description": "rows of history", "examples": "",
    }
    assert rows["prediction_length"]["range"] == "1 – 512"
    assert rows["prediction_offset"]["default"] == "0"
    assert rows["method"]["range"] == 'one of "mean", "median"' and rows["method"]["default"] == '"mean"'
    assert rows["alpha"]["type"] == "number or null" and rows["alpha"]["range"] == "> 0, < 1"


def test_card_status_and_notes():
    card = mc.model_card(_extras(
        parameters=PARAMETERS,
        card_valid="true",
        card_validation={"valid": True, "issues": [
            {"severity": "warning", "path": "license", "message": "no license"},
            {"severity": "error", "path": "x", "message": "bad"},
        ]},
    ))
    assert card["valid"] is True
    assert [i["path"] for i in card["warnings"]] == ["license"]
    assert [i["path"] for i in card["errors"]] == ["x"]
    assert card["unknown_keys_rejected"] is True
    assert card["rules"] == ["history_length + prediction_offset <= rows"]


def test_inputs_and_outputs():
    card = mc.model_card(_extras(
        inputs=[{"file": "input.parquet", "minRows": 3, "columns": [
            {"position": 0, "role": "time", "type": ["date", "datetime"]},
            {"position": 2, "role": "covariate", "type": "number", "nullable": True, "required": False},
            {"name": "Region", "role": "filter", "type": "string", "requiredValues": ["Bundesweit"]},
        ]}],
        outputs=[{"file": "predictions.tsv", "columns": [
            {"nameFrom": {"inputRole": "target", "suffix": "_q10"}, "role": "quantile", "level": 0.1, "type": "number"},
            {"name": "date", "role": "time"},
        ]}],
    ))
    f = card["inputs"][0]
    assert f["file"] == "input.parquet" and f["notes"] == "at least 3 rows"
    assert [c["where"] for c in f["columns"]] == ["column 1", "column 3", "Region"]
    assert f["columns"][0]["type"] == "date, datetime"
    assert f["columns"][1]["notes"] == "gaps allowed; optional"
    assert f["columns"][2]["notes"] == 'must contain "Bundesweit"'
    assert [c["role_label"] for c in f["columns"]] == ["Time axis", "Extra predictor", "Selects the rows used"]
    out = card["outputs"][0]["columns"]
    assert out[0]["where"] == "<target column>_q10" and out[0]["role"] == "quantile 0.1"
    assert out[0]["role_label"] == "10th percentile"
    assert out[1]["where"] == "date" and out[1]["role_label"] == "Time of the forecast step"


def test_percentile_labels_and_unknown_roles():
    assert [mc._percentile(x) for x in (0.1, 0.9, 0.025, 0.01, 0.5)] == [
        "10th percentile", "90th percentile", "2.5th percentile", "1st percentile", "50th percentile"]
    assert mc._percentile("x") == "" and mc._percentile(None) == ""
    card = mc.model_card(_extras(outputs=[{"file": "p.tsv", "columns": [
        {"name": "q", "role": "quantile"}, {"name": "z", "role": "new-role"}]}]))
    cols = card["outputs"][0]["columns"]
    assert cols[0]["role_label"] == "Quantile of the forecast" and cols[0]["role"] == "quantile"
    assert cols[1]["role_label"] == "" and cols[1]["role"] == "new-role"


def test_resources_documentation_and_no_task():
    card = mc.model_card(_extras(
        task={"type": "forecast", "probabilistic": True, "maxHorizon": 512, "parameterRoles": {"horizon": "prediction_length"}},
        resources={"gpu": 0, "network": True},
        documentation={"method": "zero-shot", "references": ["https://example.org", "a paper"]},
    ))
    assert "task" not in card and "parameter_roles" not in card
    assert ("Needs internet", "yes") in card["resources"] and ("GPUs", "0") in card["resources"]
    assert card["documentation"] == [("Method", "zero-shot")]
    assert card["references"] == ["https://example.org", "a paper"]


def test_malformed_sections_do_not_break_the_tab():
    card = mc.model_card(_extras(parameters="{not json", inputs={"file": "x"}, resources=[1], card_valid="maybe",
                                 card_validation="null"))
    assert card["parameters"] == [] and card["inputs"] == [] and card["resources"] == []
    assert card["valid"] is None and card["errors"] == []


def test_card_extras_are_the_sync_flows():
    assert mc.CARD_EXTRAS == {
        "model_task", "model_parameters", "model_inputs", "model_outputs", "model_resources",
        "model_documentation", "model_card_valid", "model_card_validation",
    }
