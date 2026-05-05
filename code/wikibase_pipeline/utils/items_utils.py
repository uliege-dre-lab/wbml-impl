from ..wikibase_api import WikibaseAPI
from .verbose_utils import warn

ITEM_PREFIX = "urn:wikibase:item:"


def search_item_by_labels(
    wikibase_api: WikibaseAPI,
    labels: dict[str, str],
    default_language: str,
    verbose: int,
) -> str | None:
    """
    Search Wikibase for an item using an exact label match.
    Label priority for the search term:
    - Default language label
    - Any other available label (arbitrary order)
    - No labels at all → return None immediately
    Inputs:
    - wikibase_api: An instance of the WikibaseAPI class.
    - labels: A dictionary mapping language codes to label strings.
    - default_language: The default language code to prioritize for label matching.
    - verbose: Verbosity level for logging.
    Output:
    - The first QID of the matched item if found, otherwise None.
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
    """
    Clean up a text value from Wikibase.
    Input:
    - value: The value to clean (can be of any type).
    Output:
    - The cleaned-up text value, or None if the input is None.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"none", "null", "nan"}:
        return None
    return text


def normalize_text(value) -> str | None:
    """
    Normalize a text value from Wikibase.
    Input:
    - value: The value to normalize (can be of any type).
    Output:
    - The normalized text value, or None if the input is None.
    """
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def iri_suffix(iri: str) -> str:
    """
    Extract the suffix from a Wikibase item or property IRI.
    Input:
    - iri: The IRI string to extract the suffix from.
    Output:
    - The suffix string.
    """
    return iri.split(ITEM_PREFIX, 1)[-1]
