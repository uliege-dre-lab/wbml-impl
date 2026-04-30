from .verbose_utils import warn

ITEM_PREFIX = "urn:wikibase:item:"


def search_item_by_labels(
    wikibase_api,
    labels: dict[str, str],
    default_language: str,
    verbose: int = 0,
) -> str | None:
    """
    Search Wikibase for an item using an exact label match.

    Label priority for the search term:
      1. Default language label
      2. Any other available label (arbitrary order)
      3. No labels at all → return None immediately

    - One result   → return it.
    - Multiple     → warn and return the first (no guarantee of correctness).
    - No results   → return None (caller will create).
    """
    label_value = labels.get(default_language)
    search_lang = default_language

    if label_value is None:
        for lang, value in labels.items():
            label_value = value
            search_lang = lang
            break  # take the first available language

    if label_value is None:
        return None  # no labels at all (should not happen after collect fallback)

    results = list(
        wikibase_api.search_items_by_label(label_value, language=search_lang)
    )

    if not results:
        return None

    if len(results) == 1:
        return results[0]

    warn(
        f"  Multiple items found for label '{label_value}'@{search_lang}: "
        f"{results} — taking the first one ({results[0]}), "
        f"cannot guarantee correctness.",
        verbose,
    )
    return results[0]


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "nan"}:
        return None
    return text


def normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def iri_suffix(iri: str) -> str:
    return iri.split(ITEM_PREFIX, 1)[-1]
