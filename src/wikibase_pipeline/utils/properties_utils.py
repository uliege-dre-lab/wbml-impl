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
) -> str | None:
    """
    Search Wikibase for a property matching both label (in priority order)
    and expected datatype.

    Returns:
      - PID if exactly one valid match
      - None if zero or multiple matches
    """
    tried_values: set[str] = set()
    matching_pids: set[str] = set()

    priority_langs = [default_language, ""]
    other_langs = [lang for lang in labels if lang not in priority_langs]

    for lang in priority_langs + other_langs:
        label = labels.get(lang)
        if label is None or label in tried_values:
            continue
        tried_values.add(label)

        search_lang = lang if lang else default_language
        candidates = wikibase_api.search_properties_by_label(
            label, language=search_lang
        )

        for pid in candidates:
            try:
                actual_dt = wikibase_api.get_property_datatype(pid)
            except Exception:
                continue

            if actual_dt == expected_datatype:
                matching_pids.add(pid)

    # decision phase
    if len(matching_pids) == 1:
        return next(iter(matching_pids))

    return None
