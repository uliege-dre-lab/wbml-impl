ITEM_PREFIX = "urn:wikibase:item:"


def search_item_by_labels(
    wikibase_api,
    labels: dict[str, str],
    default_language: str,
    lookup: dict | None = None,
    current_iri: str | None = None,
) -> str | None:
    """
    Search Wikibase for an item using labels in priority order:
      1. collect candidates for all labels
      2. keep only candidates with no conflicting label values
      (i.e. for every language where both sides have a label, the values must match).
    Returns the QID if exactly one compatible candidate is found, else None.
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
        for qid in wikibase_api.search_items_by_label(label, language=search_lang):
            if qid not in seen:
                seen.add(qid)
                candidates.append(qid)

    compatible: list[str] = []
    for qid in candidates:
        try:
            entity = wikibase_api.get_entity(qid, props="labels")
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
            compatible.append(qid)

    if len(compatible) == 1:
        return compatible[0]

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
