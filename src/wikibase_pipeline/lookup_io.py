import json
from pathlib import Path

from .utils.verbose_utils import inform, warn


def load_lookup(path: str | Path, verbose) -> dict:
    empty_lookup = {"items": {}, "properties": {}, "statements": {}, "references": {}}
    if path is None:
        return empty_lookup

    path = Path(path)
    if not path.exists():
        return empty_lookup

    inform(f"Loading lookup from {path}", verbose)

    data = json.loads(path.read_text(encoding="utf-8"))

    for key in ("items", "properties"):
        if key not in data:
            warn(f"Missing '{key}' section in lookup, initializing it.", verbose)
            data[key] = {}

    # statements and references are rebuilt each run from Wikibase
    data["statements"] = {}
    data["references"] = {}

    inform("Lookup successfully loaded.", verbose)

    return data


def save_lookup(path: str | Path, lookup: dict, verbose) -> None:
    path = Path(path)

    inform(f"Saving lookup to {path}", verbose)

    path.parent.mkdir(parents=True, exist_ok=True)

    persisted_lookup = {}
    for key in ("items", "properties"):
        value = lookup.get(key, {})
        if not isinstance(value, dict):
            raise ValueError(
                f"Invalid lookup structure: section '{key}' "
                f"must be a dict, got {type(value).__name__}."
            )
        persisted_lookup[key] = value

    path.write_text(
        json.dumps(persisted_lookup, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    inform("Lookup successfully saved.", verbose)


def validate_lookup_cache(lookup: dict, wb_api, verbose) -> None:
    """
    Batch-check every cached QID/PID against Wikibase and evict any
    that no longer exist.  Stale entries are removed in-place so the
    normal resolver fallback (label search → create) takes over.
    """
    item_iris = {iri: qid for iri, qid in lookup.get("items", {}).items() if qid}
    prop_iris = {
        iri: entry["id"]
        for iri, entry in lookup.get("properties", {}).items()
        if isinstance(entry, dict) and entry.get("id")
    }

    all_ids = list(set(item_iris.values()) | set(prop_iris.values()))
    if not all_ids:
        return

    inform(f"Validating {len(all_ids)} cached IDs against Wikibase…", verbose)
    existing = wb_api.filter_existing_ids(all_ids)

    # Evict stale items
    stale_item_iris = [iri for iri, qid in item_iris.items() if qid not in existing]
    for iri in stale_item_iris:
        stale_qid = lookup["items"].pop(iri)
        warn(
            f"Evicting stale item from cache: <{iri}> → {stale_qid} "
            f"(entity no longer exists in Wikibase).",
            verbose,
        )

    # Evict stale properties
    stale_prop_iris = [iri for iri, pid in prop_iris.items() if pid not in existing]
    for iri in stale_prop_iris:
        stale_pid = lookup["properties"].pop(iri)["id"]
        warn(
            f"Evicting stale property from cache: <{iri}> → {stale_pid} "
            f"(entity no longer exists in Wikibase).",
            verbose,
        )

    evicted = len(stale_item_iris) + len(stale_prop_iris)
    if evicted:
        inform(
            f"Evicted {evicted} stale cache entries. They will be re-resolved.", verbose
        )
    else:
        inform("All cached IDs are valid.", verbose)
