from unittest.mock import MagicMock

from wikibase_pipeline.utils.items_utils import search_item_by_labels


def make_api(search_results=None, entities=None):
    """
    search_results: dict mapping label_string → list of QIDs returned by search
    entities: dict mapping QID → {"labels": {...}, "aliases": {...}}
    """
    api = MagicMock()

    def search_side_effect(label, language="en"):
        return (search_results or {}).get(label, [])

    def get_entity_side_effect(qid, props="labels|aliases"):
        return (entities or {}).get(qid, {"labels": {}, "aliases": {}})

    api.search_items_by_label.side_effect = search_side_effect
    api.get_entity.side_effect = get_entity_side_effect
    return api


def wb_entity(labels=None, aliases=None):
    return {
        "labels": {lang: {"value": v} for lang, v in (labels or {}).items()},
        "aliases": {
            lang: [{"value": v} for v in vals] for lang, vals in (aliases or {}).items()
        },
    }


def test_single_best_match_returned():
    api = make_api(
        search_results={"cat": ["Q1"]},
        entities={"Q1": wb_entity(labels={"en": "cat"})},
    )
    assert search_item_by_labels(api, {"en": "cat"}, "en") == "Q1"


def test_no_candidates_returns_none():
    api = make_api(search_results={}, entities={})
    assert search_item_by_labels(api, {"en": "cat"}, "en") is None


def test_zero_score_returns_none():
    api = make_api(
        search_results={"cat": ["Q1"]},
        entities={"Q1": wb_entity(labels={"en": "dog"})},
    )
    assert search_item_by_labels(api, {"en": "cat"}, "en") is None


def test_tie_returns_none():
    api = make_api(
        search_results={"cat": ["Q1", "Q2"]},
        entities={
            "Q1": wb_entity(labels={"en": "cat"}),
            "Q2": wb_entity(labels={"en": "cat"}),
        },
    )
    assert search_item_by_labels(api, {"en": "cat"}, "en") is None


def test_best_score_wins():
    # Q1 matches on label (+3), Q2 only on alias (+2)
    api = make_api(
        search_results={"cat": ["Q1", "Q2"]},
        entities={
            "Q1": wb_entity(labels={"en": "cat"}),
            "Q2": wb_entity(aliases={"en": ["cat"]}),
        },
    )
    assert search_item_by_labels(api, {"en": "cat"}, "en") == "Q1"


def test_search_also_uses_incoming_aliases():
    # Wikibase is searched using an alias from A, not a label
    api = make_api(
        search_results={"kitty": ["Q1"]},
        entities={"Q1": wb_entity(labels={"en": "cat"}, aliases={"en": ["kitty"]})},
    )
    result = search_item_by_labels(api, {"en": "cat"}, "en", aliases={"en": ["kitty"]})
    assert result == "Q1"


def test_alias_in_A_matches_label_in_B():
    api = make_api(
        search_results={"kitty": ["Q1"]},
        entities={"Q1": wb_entity(labels={"en": "kitty"})},
    )
    result = search_item_by_labels(api, {}, "en", aliases={"en": ["kitty"]})
    assert result == "Q1"
