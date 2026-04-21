import json
from pathlib import Path

from .utils.verbose_utils import inform, warn


def load_lookup(path: str | Path, verbose) -> dict:
    path = Path(path)

    if not path.exists():
        return {"items": {}, "properties": {}, "statements": {}, "references": {}}

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
