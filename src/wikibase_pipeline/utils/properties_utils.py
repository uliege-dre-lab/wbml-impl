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
    Search Wikibase for a property matching both label (all languages searched)
    and expected datatype, then filtered by label compatibility.
    Returns the PID if exactly one compatible match is found, else None.
    """
    tried_values: set[str] = set()
    candidates: list[str] = []
    seen: set[str] = set()

    priority_langs = [default_language, ""]
    other_langs = [lang for lang in labels if lang not in priority_langs]

    for lang in priority_langs + other_langs:
        label = labels.get(lang)
        if label is None or label in tried_values:
            continue
        tried_values.add(label)

        search_lang = lang if lang else default_language
        for pid in wikibase_api.search_properties_by_label(label, language=search_lang):
            if pid not in seen:
                seen.add(pid)
                candidates.append(pid)

    compatible: list[str] = []
    for pid in candidates:
        # Datatype filter
        try:
            actual_dt = wikibase_api.get_property_datatype(pid)
        except Exception:
            continue
        if actual_dt != expected_datatype:
            continue

        # Label-compatibility filter
        try:
            entity = wikibase_api.get_entity(pid, props="labels")
        except Exception:
            continue

        wb_labels: dict[str, str] = {
            lang: info["value"] for lang, info in entity.get("labels", {}).items()
        }

        conflict = any(
            labels.get(lang) is not None and labels[lang].strip() != wb_value.strip()
            for lang, wb_value in wb_labels.items()
        )

        if not conflict:
            compatible.append(pid)

    if len(compatible) == 1:
        return compatible[0]

    return None
