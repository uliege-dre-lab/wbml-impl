ITEM_PREFIX = "urn:wikibase:item:"

# Scoring weights
SCORE_LABEL_LABEL = 3
SCORE_LABEL_ALIAS = 2
SCORE_ALIAS_LABEL = 2
SCORE_ALIAS_ALIAS = 1


def _score_candidate(
    incoming_labels: dict[str, str],
    incoming_aliases: dict[str, list[str]],
    wb_labels: dict[str, str],
    wb_aliases: dict[str, list[str]],
) -> int:
    """
    Score how well a Wikibase candidate (B) matches the incoming data (A).

    Per language, per term in A:
      - incoming label vs wikibase label  → +3
      - incoming label vs wikibase alias  → +2
      - incoming alias vs wikibase label  → +2
      - incoming alias vs wikibase alias  → +1
    """
    score = 0
    all_langs = set(incoming_labels) | set(incoming_aliases)

    for lang in all_langs:
        wb_label_norm = wb_labels.get(lang, "").strip().lower()
        wb_alias_norms = {v.strip().lower() for v in wb_aliases.get(lang, [])}

        inc_label = incoming_labels.get(lang)
        if inc_label:
            inc_norm = inc_label.strip().lower()
            if wb_label_norm and inc_norm == wb_label_norm:
                score += SCORE_LABEL_LABEL
            elif inc_norm in wb_alias_norms:
                score += SCORE_LABEL_ALIAS

        inc_label_norm = incoming_labels.get(lang, "").strip().lower()

        for alias in incoming_aliases.get(lang, []):
            alias_norm = alias.strip().lower()
            if alias_norm == inc_label_norm:
                continue
            if wb_label_norm and alias_norm == wb_label_norm:
                score += SCORE_ALIAS_LABEL
            elif alias_norm in wb_alias_norms:
                score += SCORE_ALIAS_ALIAS

    return score


def search_item_by_labels(
    wikibase_api,
    labels: dict[str, str],
    default_language: str,
    aliases: dict[str, list[str]] | None = None,
    lookup: dict | None = None,
    current_iri: str | None = None,
) -> str | None:
    """
    Search Wikibase for an item using a scoring approach.

    Let A = incoming labels + aliases, B = candidate's labels + aliases.
    Scoring per language:
      - label(A) vs label(B): +3
      - label(A) vs alias(B): +2
      - alias(A) vs label(B): +2
      - alias(A) vs alias(B): +1

    Returns:
      - QID of the unique highest-scoring candidate (score > 0)
      - None if no candidate scores > 0, or if there is a tie
    """
    if aliases is None:
        aliases = {}

    # Collect candidates by searching all label and alias values
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
        for qid in wikibase_api.search_items_by_label(value, language=search_lang):
            if qid not in seen:
                seen.add(qid)
                candidates.append(qid)

    for lang, alias_list in aliases.items():
        search_lang = lang if lang else default_language
        for alias_value in alias_list:
            if alias_value in tried_values:
                continue
            tried_values.add(alias_value)
            for qid in wikibase_api.search_items_by_label(
                alias_value, language=search_lang
            ):
                if qid not in seen:
                    seen.add(qid)
                    candidates.append(qid)

    if not candidates:
        return None

    # Score each candidate
    scores: dict[str, int] = {}
    for qid in candidates:
        try:
            entity = wikibase_api.get_entity(qid, props="labels|aliases")
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
            scores[qid] = s

    if not scores:
        return None

    max_score = max(scores.values())
    best = [qid for qid, s in scores.items() if s == max_score]

    if len(best) == 1:
        return best[0]

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


def normalize_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def iri_suffix(iri: str) -> str:
    return iri.split(ITEM_PREFIX, 1)[-1]
