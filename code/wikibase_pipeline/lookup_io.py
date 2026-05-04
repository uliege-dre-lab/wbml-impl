import json
from pathlib import Path

from .utils.verbose_utils import inform, warn
from .wikibase_api import WikibaseAPI


def load_lookup(path: str | Path, verbose: int) -> dict:
    """
    Load the lookup cache from a JSON file.
    If the file does not exist, return an empty lookup structure.
    Input:
    - path: Path to the lookup JSON file.
    - verbose: Verbosity level for logging.
    Output:
    - A dictionary with the lookup data, containing 'items', 'properties',
      'statements', and 'references' sections.
    """
    empty_lookup = {"items": {}, "properties": {}, "statements": {}, "references": {}}
    if path is None:
        inform(
            "No lookup file path provided. Starting with an empty lookup cache.",
            verbose,
        )
        return empty_lookup

    path = Path(path)
    if not path.exists():
        warn("Lookup file not found. Starting with an empty lookup cache.", verbose)
        return empty_lookup

    data = json.loads(path.read_text(encoding="utf-8"))

    for key in ("items", "properties"):
        if key not in data:
            data[key] = {}

    data["statements"] = {}
    data["references"] = {}

    return data


def save_lookup(path: str | Path, lookup: dict, verbose: int) -> None:
    """
    Save the lookup cache to a JSON file.
    Inputs:
    - path: Path to the lookup JSON file.
    - lookup: The lookup dictionary to save, containing 'items', 'properties'
    - verbose: Verbosity level for logging.
    """
    path = Path(path)

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


def validate_lookup_cache(lookup: dict, wb_api: WikibaseAPI, verbose: int) -> None:
    """
    Batch-check every cached QID/PID against Wikibase
    and remove any that no longer exist.
    Inputs:
    - lookup: The lookup dictionary containing 'items' and 'properties' sections.
    - wb_api: An instance of the WikibaseAPI class for making API calls.
    - verbose: Verbosity level for logging.
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

    stale_item_iris = [iri for iri, qid in item_iris.items() if qid not in existing]
    for iri in stale_item_iris:
        stale_qid = lookup["items"].pop(iri)
        inform(
            f"Evicting stale item from cache: <{iri}> → {stale_qid} "
            f"(entity no longer exists in Wikibase).",
            verbose,
        )

    stale_prop_iris = [iri for iri, pid in prop_iris.items() if pid not in existing]
    for iri in stale_prop_iris:
        stale_pid = lookup["properties"].pop(iri)["id"]
        inform(
            f"Evicting stale property from cache: <{iri}> → {stale_pid} "
            f"(entity no longer exists in Wikibase).",
            verbose,
        )

    evicted = len(stale_item_iris) + len(stale_prop_iris)
    if evicted:
        inform(f"Evicted {evicted} stale cache entries.", verbose)
    else:
        inform("All cached IDs are valid.", verbose)
