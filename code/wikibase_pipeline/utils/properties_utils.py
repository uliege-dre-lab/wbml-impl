from ..wikibase_api import WikibaseAPI

PROPERTY_PREFIX = "urn:wikibase:property:"


def lookup_get(
    lookup: dict,
    iri_str: str,
    expected_datatype: str,
    wikibase_api: WikibaseAPI,
) -> str | None:
    """
    Check lookup for an existing property entry for the given IRI.
    Inputs:
    - lookup: The lookup cache dictionary.
    - iri_str: The IRI string of the property to look up.
    - expected_datatype: The expected Wikibase datatype of the property.
    - wikibase_api: An instance of the WikibaseAPI class.
    Returns:
    - The property ID (e.g., "P123") if found and valid, or None if not found.
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
    wikibase_api: WikibaseAPI,
    labels: dict[str, str],
    default_language: str,
    expected_datatype: str,
) -> str | None:
    """
    Search Wikibase for a property using an exact label match,
    filtered by expected datatype.
    Search priority for the label:
      1. Default language label
      2. Any other available label (arbitrary order)
      3. No labels at all → return None immediately
    Inputs:
    - wikibase_api: An instance of the WikibaseAPI class.
    - labels: A dictionary of language codes to label strings.
    - default_language: The default language code to prioritize in the search.
    - expected_datatype: The expected Wikibase datatype of the property.
    Returns:
    - The property ID if found and valid, or None if not found.
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

    pid = results[0]
    actual_dt = wikibase_api.get_property_datatype(pid)
    if actual_dt != expected_datatype:
        raise ValueError(
            f"Property '{pid}' already exists with label '{label_value}'@{search_lang} "
            f"but has datatype '{actual_dt}' instead of expected '{expected_datatype}'."
            " Cannot create a duplicate — fix your Wikibase data or your mapping."
        )
    return pid


def iri_suffix(iri: str) -> str:
    """
    Extract the suffix of a property IRI by removing the known prefix.
    """
    return iri.split(PROPERTY_PREFIX, 1)[-1]
