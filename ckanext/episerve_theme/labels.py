"""Readable names for the extras on the "Additional Info" tab (the sync flows store them under technical keys).

A key not listed here is shown with its underscores as spaces and a capital first letter. Nothing here imports
CKAN, so it can be tested on its own.
"""

LABELS = {
    "access": "Access",
    "additional_type": "Category",
    "algorithm": "Algorithm",
    "benchmark_id": "Benchmark ID",
    "computation_time": "Computation time",
    "data_commit": "Data version (lakeFS commit)",
    "data_transformation_sql": "Data selection (SQL)",
    "dataset_type": "Entry type",
    "docker_image": "Container image",
    "docker_image_created": "Image built",
    "docker_tag": "Image tag",
    "executed_by": "Run by",
    "input_dataset_qids": "Input datasets",
    "input_format": "Input format",
    "input_sources": "Input files",
    "lead_researcher": "Lead researcher",
    "model": "Model",
    "model_card_valid": "Model card valid",
    "model_qid": "Model ID",
    "modified": "Last processed",
    "output_format": "Output format",
    "paper_doi": "Paper (DOI)",
    "qid": "ID (QID)",
    "run_timestamp": "Run started",
    "source_changed_at": "Source last changed",
    "source_qids": "Source datasets",
    "status": "Status",
}

# Labels that depend on the kind of entry: a dataset's ``modified`` is the downloader's nightly check (set on
# every run, changed or not), a benchmark's is when its files were generated.
BY_ENTRY_TYPE = {
    ("modified", "raw-data"): "Last checked",
    ("modified", "benchmark-data"): "Generated",
}

ENTRY_TYPES = {
    "raw-data": "Dataset",
    "benchmark-data": "Benchmark data",
    "model": "Model",
    "model-run": "Model run",
}


def label(key: str, entry_type: str | None = None) -> str:
    """The readable name of an extra; ``entry_type`` is the entry's ``dataset_type``."""
    key = key or ""
    return BY_ENTRY_TYPE.get((key, entry_type)) or LABELS.get(key) or key.replace("_", " ").strip().capitalize()


def value(key: str, raw):
    """The readable value of an extra: the entry type in words, everything else unchanged."""
    if key == "dataset_type":
        return ENTRY_TYPES.get(raw, raw)
    return raw
