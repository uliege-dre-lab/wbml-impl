from .items_utils import _score_candidate


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
    aliases: dict[str, list[str]] | None = None,
) -> str | None:
    """
    Search Wikibase for a property using the same scoring approach as items,
    additionally filtered by expected datatype.
    Returns the PID of the unique highest-scoring match, or None.
    """
    if aliases is None:
        aliases = {}

    candidates: list[str] = []
    seen: set[str] = set()
    tried_values: set[str] = set()

    priority_langs = [default_language, ""]
    other_langs = [lang for lang in labels if lang not in priority_langs]

    for lang in priority_langs + other_langs:
        value = labels.get(lang)
        if value is None or value in tried_values:
            continue
        tried_values.add(value)
        search_lang = lang if lang else default_language
        for pid in wikibase_api.search_properties_by_label(value, language=search_lang):
            if pid not in seen:
                seen.add(pid)
                candidates.append(pid)

    for lang, alias_list in aliases.items():
        search_lang = lang if lang else default_language
        for alias_value in alias_list:
            if alias_value in tried_values:
                continue
            tried_values.add(alias_value)
            for pid in wikibase_api.search_properties_by_label(
                alias_value, language=search_lang
            ):
                if pid not in seen:
                    seen.add(pid)
                    candidates.append(pid)

    if not candidates:
        return None

    scores: dict[str, int] = {}
    for pid in candidates:
        try:
            actual_dt = wikibase_api.get_property_datatype(pid)
        except Exception:
            continue
        if actual_dt != expected_datatype:
            continue

        try:
            entity = wikibase_api.get_entity(pid, props="labels|aliases")
        except Exception:
            continue

        wb_labels: dict[str, str] = {
            lang: info["value"] for lang, info in entity.get("labels", {}).items()
        }
        wb_aliases: dict[str, list[str]] = {
            lang: [entry["value"] for entry in entries]
            for lang, entries in entity.get("aliases", {}).items()
        }

        s = _score_candidate(labels, aliases, wb_labels, wb_aliases)
        if s > 0:
            scores[pid] = s

    if not scores:
        return None

    max_score = max(scores.values())
    best = [pid for pid, s in scores.items() if s == max_score]

    if len(best) == 1:
        return best[0]

    return None
