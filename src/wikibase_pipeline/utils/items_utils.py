ITEM_PREFIX = "urn:wikibase:item:"


def search_item_by_labels(
    wikibase_api,
    labels: dict[str, str],
    default_language: str,
) -> str | None:
    """
    Search Wikibase for an item using labels in priority order:
      1. Label in default_language
      2. Label with no language tag ("") — searched using default_language
      3. All other language labels, in insertion order

    Returns the first QID found, or None.
    Duplicate label values are tried only once.
    """
    tried_values: set[str] = set()

    priority_langs = [default_language, ""]
    other_langs = [lang for lang in labels if lang not in priority_langs]

    for lang in priority_langs + other_langs:
        label = labels.get(lang)
        if label is None or label in tried_values:
            continue
        tried_values.add(label)

        # Wikibase requires a valid language code
        # fall back to default for untagged literals
        search_lang = lang if lang else default_language
        results = wikibase_api.search_items_by_label(label, language=search_lang)
        if results:
            return results[0]

    return None


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "nan"}:
        return None
    return text


def iri_suffix(iri: str) -> str:
    return iri.split(ITEM_PREFIX, 1)[-1]
