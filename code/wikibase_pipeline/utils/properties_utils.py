from .verbose_utils import warn

PROPERTY_PREFIX = "urn:wikibase:property:"


def lookup_get(
    lookup: dict,
    iri_str: str,
    expected_datatype: str,
    wikibase_api,
) -> str | None:
    """
    Check lookup for an existing property entry for the given IRI.
    - Returns the PID if found with matching datatype.
    - Raises ValueError if found with wrong datatype.
    - Returns None if not found.
    """
    entry = lookup.get("properties", {}).get(iri_str)
    if entry is None:
        return None

    pid = entry["id"]
    stored_datatype = entry.get("datatype")

    if stored_datatype is None:
        stored_datatype = wikibase_api.get_property_datatype(pid)
        entry["datatype"] = stored_datatype

    if stored_datatype != expected_datatype:
        raise ValueError(
            f"Property datatype mismatch for <{iri_str}>: "
            f"lookup has pid={pid!r} with datatype={stored_datatype!r}, "
            f"but expected {expected_datatype!r}. "
            "Please fix or remove the lookup entry."
        )

    return pid


def search_wikibase_properties(
    wikibase_api,
    labels: dict[str, str],
    default_language: str,
    expected_datatype: str,
    verbose: int = 0,
) -> str | None:
    """
    Search Wikibase for a property using an exact label match,
    filtered by expected datatype.

    Label priority for the search term:
      1. Default language label
      2. Any other available label (arbitrary order)
      3. No labels at all → return None immediately

    Among the results that match the expected datatype:
    - One match    → return it.
    - Multiple     → warn and return the first (no guarantee of correctness).
    - No match     → return None (caller will create).
    """
    label_value = labels.get(default_language)
    search_lang = default_language

    if label_value is None:
        for lang, value in labels.items():
            label_value = value
            search_lang = lang
            break

    if label_value is None:
        return None

    results = list(
        wikibase_api.search_properties_by_label(label_value, language=search_lang)
    )

    if not results:
        return None

    # Filter by expected datatype
    valid: list[str] = []
    for pid in results:
        try:
            actual_dt = wikibase_api.get_property_datatype(pid)
        except Exception:
            continue
        if actual_dt == expected_datatype:
            valid.append(pid)

    if not valid:
        return None

    if len(valid) == 1:
        return valid[0]

    warn(
        f"  Multiple properties found for label '{label_value}'@{search_lang} "
        f"with datatype '{expected_datatype}': {valid} "
        f"— taking the first one ({valid[0]}), cannot guarantee correctness.",
        verbose,
    )
    return valid[0]


def iri_suffix(iri: str) -> str:
    return iri.split(PROPERTY_PREFIX, 1)[-1]
