"""Turn the model card extras of a CKAN model entry into rows for the "Model card" tab.

The sync flow (workflow-prefect__sync-lakefs-ckan) stores each section of a model's card
(spec model-card v1 of episerve_specs) as a JSON extra: model_task, model_parameters,
model_inputs, model_outputs, model_resources, model_documentation, plus model_card_valid
and model_card_validation. Nothing here imports CKAN, so it can be tested on its own.
Every function tolerates a missing or malformed section: the tab shows what is there.
"""

import json

SECTIONS = ("task", "parameters", "inputs", "outputs", "resources", "documentation")
CARD_EXTRAS = {f"model_{s}" for s in SECTIONS} | {"model_card_valid", "model_card_validation"}


def _json(value):
    if not isinstance(value, str) or not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def _text(value) -> str:
    """A value as shown on the page: JSON-ish for lists and booleans, plain otherwise."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(_text(v) for v in value)
    if isinstance(value, (dict,)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _quoted(values) -> str:
    return ", ".join(json.dumps(v, ensure_ascii=False) for v in values)


def param_type(spec: dict) -> str:
    """E.g. "integer (steps)", "string or null"."""
    types = spec.get("type")
    text = " or ".join(types) if isinstance(types, list) else (types or "any")
    return f"{text} ({spec['unit']})" if spec.get("unit") else text


def param_range(spec: dict) -> str:
    """The allowed values: "1 – 512", "≥ 3", "one of …", length or pattern limits; "" when unrestricted."""
    if "enum" in spec and isinstance(spec["enum"], list):
        return "one of " + _quoted(spec["enum"])
    parts = []
    low = ("≥", spec["minimum"]) if "minimum" in spec else (">", spec["exclusiveMinimum"]) if "exclusiveMinimum" in spec else None
    high = ("≤", spec["maximum"]) if "maximum" in spec else ("<", spec["exclusiveMaximum"]) if "exclusiveMaximum" in spec else None
    if low and high and low[0] == "≥" and high[0] == "≤":
        parts.append(f"{_text(low[1])} – {_text(high[1])}")
    else:
        parts += [f"{bound[0]} {_text(bound[1])}" for bound in (low, high) if bound]
    if "multipleOf" in spec:
        parts.append(f"multiple of {_text(spec['multipleOf'])}")
    if "minLength" in spec or "maxLength" in spec:
        parts.append(f"length {_text(spec.get('minLength', 0))} – {_text(spec.get('maxLength', '…'))}")
    if "pattern" in spec:
        parts.append(f"matches {spec['pattern']}")
    return ", ".join(parts)


def parameter_rows(parameters) -> list[dict]:
    if not isinstance(parameters, dict) or not isinstance(parameters.get("properties"), dict):
        return []
    required = set(parameters.get("required") or [])
    rows = []
    for name, spec in parameters["properties"].items():
        spec = spec if isinstance(spec, dict) else {}
        rows.append({
            "name": name,
            "required": name in required,
            "type": param_type(spec),
            "default": json.dumps(spec["default"], ensure_ascii=False) if "default" in spec else "",
            "range": param_range(spec),
            "description": spec.get("description") or spec.get("title") or "",
            "examples": _quoted(spec["examples"]) if isinstance(spec.get("examples"), list) else "",
        })
    return rows


# Plain words for the column roles of spec model-card v1; the code stays visible next to them.
INPUT_ROLES = {
    "time": "Time axis",
    "target": "Series to forecast",
    "group": "Splits the data into separate series",
    "covariate": "Extra predictor",
    "filter": "Selects the rows used",
    "other": "Other",
}
OUTPUT_ROLES = {
    "time": "Time of the forecast step",
    "group": "Series the row belongs to",
    "mean": "Mean forecast",
    "median": "Median forecast",
    "point": "Point forecast",
    "quantile": "Quantile of the forecast",
    "sample": "One simulated outcome",
    "other": "Other",
}


def _ordinal(number) -> str:
    """10 -> "10th", 2.5 -> "2.5th", 1 -> "1st"."""
    if isinstance(number, float) and number.is_integer():
        number = int(number)
    if isinstance(number, int) and number % 100 not in (11, 12, 13):
        return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"
    return f"{number}th"


def _percentile(level) -> str:
    """0.1 -> "10th percentile"."""
    if not isinstance(level, (int, float)) or isinstance(level, bool):
        return ""
    return f"{_ordinal(round(level * 100, 6))} percentile"


def _input_column(col: dict) -> dict:
    notes = []
    if col.get("nullable"):
        notes.append("gaps allowed")
    if col.get("required") is False:
        notes.append("optional")
    if isinstance(col.get("requiredValues"), list):
        notes.append("must contain " + _quoted(col["requiredValues"]))
    if isinstance(col.get("values"), list):
        notes.append("values " + _quoted(col["values"]))
    return {
        "where": col["name"] if col.get("name") else (f"column {col['position'] + 1}" if isinstance(col.get("position"), int) else ""),
        "role": col.get("role", ""),
        "role_label": INPUT_ROLES.get(col.get("role"), ""),
        "type": _text(col.get("type")),
        "notes": "; ".join(notes),
        "description": col.get("description", ""),
    }


def _output_column(col: dict) -> dict:
    if col.get("name"):
        name = col["name"]
    elif isinstance(col.get("nameFrom"), dict):
        name = f"<{col['nameFrom'].get('inputRole', '?')} column>{col['nameFrom'].get('suffix', '')}"
    else:
        name = ""
    role = col.get("role", "")
    label = OUTPUT_ROLES.get(role, "")
    if role == "quantile" and _percentile(col.get("level")):
        label = _percentile(col.get("level"))
        role = f"quantile {_text(col['level'])}"
    return {"where": name, "role": role, "role_label": label, "type": _text(col.get("type")),
            "notes": "optional" if col.get("required") is False else "", "description": col.get("description", "")}


def file_rows(files, output: bool = False) -> list[dict]:
    if not isinstance(files, list):
        return []
    rows = []
    for f in files:
        if not isinstance(f, dict):
            continue
        columns = [c for c in f.get("columns") or [] if isinstance(c, dict)]
        notes = []
        if f.get("required") is False:
            notes.append("optional file")
        if "minRows" in f:
            notes.append(f"at least {_text(f['minRows'])} rows")
        if not output and f.get("additionalColumns") is False:
            notes.append("no further columns")
        rows.append({
            "file": f.get("file", ""),
            "format": f.get("format", ""),
            "description": f.get("description", ""),
            "notes": "; ".join(notes),
            "columns": [(_output_column if output else _input_column)(c) for c in columns],
        })
    return rows


_TASK_LABELS = {"type": "Task", "frequency": "Frequency", "probabilistic": "Probabilistic (quantiles)",
                "covariates": "Uses further input columns", "maxHorizon": "Longest forecast (steps)"}
_RESOURCE_LABELS = {"cpu": "CPU", "memory": "Memory", "gpu": "GPUs", "network": "Needs internet",
                    "typicalRuntimeSeconds": "Typical runtime (s)"}
_DOC_LABELS = {"method": "Method", "intendedUse": "Intended use", "limitations": "Limitations",
               "trainingData": "Training data"}


def _pairs(section, labels: dict) -> list[tuple[str, str]]:
    if not isinstance(section, dict):
        return []
    return [(labels.get(k, k), _text(v)) for k, v in section.items() if k in labels]


def model_card(extras) -> dict | None:
    """Everything the "Model card" tab shows, or None when the entry has no card extras.

    ``extras`` is CKAN's list of ``{"key", "value"}`` dicts (or a plain dict).
    """
    if isinstance(extras, list):
        extras = {e.get("key"): e.get("value") for e in extras if isinstance(e, dict)}
    extras = extras or {}
    if not any(k in extras for k in CARD_EXTRAS):
        return None
    sections = {s: _json(extras.get(f"model_{s}")) for s in SECTIONS}
    validation = _json(extras.get("model_card_validation")) or {}
    issues = [i for i in validation.get("issues") or [] if isinstance(i, dict)]
    valid = {"true": True, "false": False}.get(str(extras.get("model_card_valid", "")).lower())
    parameters = sections["parameters"] if isinstance(sections["parameters"], dict) else {}
    task = sections["task"] if isinstance(sections["task"], dict) else {}
    roles = task.get("parameterRoles") if isinstance(task.get("parameterRoles"), dict) else {}
    documentation = sections["documentation"] if isinstance(sections["documentation"], dict) else {}
    refs = documentation.get("references")
    return {
        "valid": valid,
        "errors": [i for i in issues if i.get("severity") == "error"],
        "warnings": [i for i in issues if i.get("severity") == "warning"],
        "parameters": parameter_rows(parameters),
        "unknown_keys_rejected": parameters.get("additionalProperties") is False,
        "rules": [r for r in parameters.get("rules") or [] if isinstance(r, str)],
        "parameter_roles": [(role, name) for role, name in roles.items()],
        "inputs": file_rows(sections["inputs"]),
        "outputs": file_rows(sections["outputs"], output=True),
        "task": _pairs(task, _TASK_LABELS),
        "resources": _pairs(sections["resources"], _RESOURCE_LABELS),
        "documentation": _pairs(documentation, _DOC_LABELS),
        "references": [r for r in (refs if isinstance(refs, list) else []) if isinstance(r, str)],
    }
