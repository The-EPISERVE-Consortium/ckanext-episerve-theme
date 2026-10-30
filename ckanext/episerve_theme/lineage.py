"""The "Lineage" tab: turn the API's upstream lineage (OpenLineage events) into a diagram and a list of steps.

The page asks ``/lineage-view/<QID>`` (plugin.py) when the tab is opened; that route fetches
``GET /lineage/events?object=<QID>`` from the API server inside the cluster and returns ``view(...)``:
a Mermaid flowchart (files and sources as boxes, jobs as rounded boxes, read -> job -> written) and
the same as rows with links to the objects' CKAN pages. Nothing here imports CKAN, so it can be tested
on its own.
"""

import re
from typing import Callable
from urllib.parse import urlsplit

_QID = re.compile(r"[Qq]\d{6,}")
_PLATFORM_FILE = re.compile(r"(Q\d{6,})(?:/(.+))?")
_OLD_BENCHMARK_FILE = re.compile(r"(\d+)/([^/]+)")   # benchmark files filed under the benchmark id (older layout)


def qid_for(pkg: dict) -> str | None:
    """The QID whose lineage the page shows, or None (no tab): models have no upstream lineage."""
    if any((g or {}).get("name") == "type-model" for g in pkg.get("groups") or []):
        return None
    name = pkg.get("name") or ""
    return name.upper() if _QID.fullmatch(name) else None


def valid_qid(qid: str) -> bool:
    return bool(_QID.fullmatch(qid or ""))


def _label(text: str) -> str:
    """Text for a Mermaid label in double quotes: no markup, no quotes."""
    text = re.sub(r"[<>&\"`]", lambda m: {"<": "‹", ">": "›", "&": "+", '"': "'", "`": "'"}[m.group()], str(text))
    return text.replace("\n", " ")


def _short(text: str, limit: int = 42) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


_SOURCE_NAMES = {"robert-koch-institut": "RKI", "api.open-meteo.com": "Open-Meteo",
                 "xmart-api-public.who.int": "WHO"}


def source_name(uri: str) -> str:
    """A short name for an external source: "RKI (GitHub)", "Open-Meteo", "WHO", otherwise the host."""
    parts = urlsplit(uri)
    host = parts.netloc or uri
    if host in ("raw.githubusercontent.com", "github.com"):
        owner = parts.path.strip("/").split("/", 1)[0]
        return f"{_SOURCE_NAMES.get(owner, owner)} (GitHub)" if owner else "GitHub"
    return _SOURCE_NAMES.get(host, host)


def _dataset_info(entry: dict, doip_namespace: str, api_url: str = "") -> dict:
    """Label, version and file URL of an OpenLineage dataset (the download URL is set in ``view``).

    Files in lakeFS (``lakefs://<repo>``) are inside the cluster: they are never linked. A benchmark file in
    the older layout (``lakefs://benchmarks`` + ``<id>/<file>``) links to the benchmark's page on the API.
    """
    namespace, name = entry.get("namespace", ""), entry.get("name", "")
    facets = entry.get("facets") or {}
    version = ((facets.get("version") or {}).get("datasetVersion")) or ""
    if namespace.startswith("lakefs://"):
        repo = namespace[len("lakefs://"):]
        old = _OLD_BENCHMARK_FILE.fullmatch(name) if repo == "benchmarks" else None
        if old:
            page = f"{api_url.rstrip('/')}/ui/benchmarks/{old.group(1)}" if api_url else None
            return {"key": f"{namespace}|{name}", "label": f"benchmark {old.group(1)}: {old.group(2)}", "qid": None,
                    "file_url": page, "page": True, "full_version": version, "version": version[:8], "external": False}
        return {"key": f"{namespace}|{name}", "label": f"{repo}: {name}", "qid": None, "file_url": None,
                "page": True, "full_version": version, "version": version[:8], "external": False}
    match = _PLATFORM_FILE.fullmatch(name) if namespace == doip_namespace else None
    if match:
        qid, file = match.group(1), match.group(2) or ""
        file_url = f"{doip_namespace}/doip/retrieve/{qid}" + (f"/{file}" if file else "")
        return {"key": f"{namespace}|{name}", "label": file or qid, "qid": qid, "file_url": file_url,
                "full_version": version, "version": version[:8], "external": False}
    uri = (facets.get("dataSource") or {}).get("uri") or (f"{namespace}/{name}" if "://" in namespace else name)
    return {"key": f"{namespace}|{name}", "label": source_name(uri), "qid": None, "file_url": uri,
            "full_version": "", "version": "", "external": True}


def platform_qids(result: dict, doip_namespace: str) -> set[str]:
    """Every platform object (QID) whose files appear in the events, to look up which are restricted."""
    qids = set()
    for event in result.get("events") or []:
        for entry in (event.get("inputs") or []) + (event.get("outputs") or []):
            info = _dataset_info(entry, doip_namespace)
            if info["qid"]:
                qids.add(info["qid"])
    return qids


def _job_info(event: dict) -> dict:
    """Label, kind, time and link of an event's job."""
    job = (event.get("job") or {}).get("name", "")
    facet = ((event.get("run") or {}).get("facets") or {}).get("episerve") or {}
    kind, qid = facet.get("kind", ""), facet.get("qid", "")
    when = (event.get("eventTime") or "")[:10]
    group, _, rest = job.partition("/")
    if group == "model-runner":
        label = f"model run: {rest.rsplit('__', 1)[-1]}"
    elif group == "benchmark":
        label = f"benchmark {rest}"
    elif group == "dataset-downloader":
        label = f"download: {rest}"
    else:
        label = job
    return {"label": label, "kind": kind, "time": when, "qid": qid,
            "url": f"/dataset/{qid.lower()}" if qid else None}


def view(result: dict, doip_namespace: str, restricted: set[str] | None = None,
         sign: Callable[[str], str] | None = None, api_url: str = "") -> dict:
    """The diagram (Mermaid source) and the steps of an upstream lineage result.

    Args:
        result: The API's answer ``{"object", "kind", "events", "unresolved", "truncated"}``.
        doip_namespace: The DOIP base URL the API uses as the namespace of platform files.
        restricted: QIDs of restricted datasets: their files are only linked when ``sign`` is given.
        sign: Turns a DOIP URL into a signed link (for a logged-in visitor); None for anonymous visitors.
        api_url: The API server's public address, for links to benchmark pages.
    """
    restricted = {q.upper() for q in restricted or ()}

    def item(info: dict) -> dict:
        """One file in the table, linked at its version when the event names one (else as it is now)."""
        url = info["file_url"]
        if info["qid"] and info["qid"] in restricted:
            url = sign(url) if sign else None     # sign the plain file URL; the version is added after
        if url and not info["external"] and not info.get("page") and info["full_version"]:
            url = f"{url}{'&' if '?' in url else '?'}version={info['full_version']}"
        return {"label": info["label"], "url": url, "version": info["version"],
                "external": info["external"], "restricted": bool(info["qid"] and info["qid"] in restricted)}
    current = (result.get("object") or "").upper()
    nodes: dict[str, dict] = {}
    lines = [
        "flowchart LR",
        "classDef data fill:#f1f5f9,stroke:#94a3b8,color:#0f172a",
        "classDef ext fill:#ffffff,stroke:#cbd5e1,color:#475569,stroke-dasharray:4 3",
        "classDef job fill:#e0f2fe,stroke:#0891b2,color:#0f172a",
        "classDef current stroke:#1e3a5f,stroke-width:3px",
    ]
    steps = []

    def node(entry: dict) -> tuple[str, dict]:
        info = _dataset_info(entry, doip_namespace, api_url)
        known = nodes.get(info["key"])
        if known is None:
            known = {**info, "id": f"d{len(nodes)}", "versions": []}
            nodes[info["key"]] = known
        if info["version"] and info["version"] not in known["versions"]:
            known["versions"].append(info["version"])
        return known["id"], info

    for index, event in enumerate(result.get("events") or []):
        job = _job_info(event)
        job_id = f"j{index}"
        when = f"<br/>{job['time']}" if job["time"] else ""
        lines.append(f'{job_id}(["{_label(job["label"])}{when}"]):::job')
        if job["qid"] and job["qid"].upper() == current:
            lines.append(f"class {job_id} current")
        inputs, outputs = [], []
        for entry in event.get("inputs") or []:
            node_id, info = node(entry)
            lines.append(f"{node_id} --> {job_id}")
            inputs.append(item(info))
        for entry in event.get("outputs") or []:
            node_id, info = node(entry)
            lines.append(f"{job_id} --> {node_id}")
            outputs.append(item(info))
        steps.append({**job, "inputs": inputs, "outputs": outputs})

    for known in nodes.values():
        version = f"<br/>@{', @'.join(known['versions'])}" if known["versions"] else ""
        qid = f"<br/>{known['qid']}" if known["qid"] and known["label"] != known["qid"] else ""
        cls = "ext" if known["external"] else "data"
        lines.append(f'{known["id"]}["{_label(_short(known["label"]))}{qid}{version}"]:::{cls}')
        if known["qid"] == current:
            lines.append(f"class {known['id']} current")

    return {
        "object": current,
        "kind": result.get("kind"),
        "mermaid": "\n".join(lines) if steps else "",
        "steps": steps,
        "unresolved": result.get("unresolved") or [],
        "truncated": result.get("truncated") or [],
    }
