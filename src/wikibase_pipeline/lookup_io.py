import json
from pathlib import Path

from .utils import inform, warn


def load_lookup(path: str | Path, verbose) -> dict:
    path = Path(path)

    if not path.exists():
        return {"builtins": {}, "items": {}, "properties": {}, "statements": {}}

    inform(f"Loading lookup from {path}", verbose)

    data = json.loads(path.read_text(encoding="utf-8"))

    # ensure structure
    for key in ("builtins", "items", "properties", "statements"):
        if key not in data:
            warn(f"Missing '{key}' section in lookup, initializing it.", verbose)
            data[key] = {}

    inform("Lookup successfully loaded.", verbose)

    return data


def save_lookup(path: str | Path, lookup: dict, verbose) -> None:
    path = Path(path)

    inform(f"Saving lookup to {path}", verbose)

    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(lookup, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    inform("Lookup successfully saved.", verbose)
