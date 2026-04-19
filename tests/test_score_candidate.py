from wikibase_pipeline.utils.items_utils import _score_candidate


def test_label_vs_label():
    assert _score_candidate({"en": "foo"}, {}, {"en": "foo"}, {}) == 3


def test_label_vs_alias():
    assert _score_candidate({"en": "foo"}, {}, {"en": "bar"}, {"en": ["foo"]}) == 2


def test_alias_vs_label():
    assert _score_candidate({}, {"en": ["foo"]}, {"en": "foo"}, {}) == 2


def test_alias_vs_alias():
    assert _score_candidate({}, {"en": ["foo"]}, {}, {"en": ["foo"]}) == 1


def test_no_match():
    assert _score_candidate({"en": "foo"}, {}, {"en": "bar"}, {}) == 0


def test_case_insensitive():
    assert _score_candidate({"en": "Foo"}, {}, {"en": "foo"}, {}) == 3


def test_multiple_languages():
    score = _score_candidate(
        {"en": "cat", "fr": "chat"},
        {},
        {"en": "cat", "fr": "chat"},
        {},
    )
    assert score == 6  # +3 for en, +3 for fr


def test_no_cross_language_match():
    # "cat" in en should not match "cat" stored under fr
    assert _score_candidate({"en": "cat"}, {}, {"fr": "cat"}, {}) == 0


def test_same_value_label_and_alias_in_A_not_double_counted():
    # "foo" is both label and alias in A — should only score as label (+3), not +3+2
    score = _score_candidate({"en": "foo"}, {"en": ["foo"]}, {"en": "foo"}, {})
    assert score == 3


def test_multiple_aliases():
    score = _score_candidate(
        {},
        {"en": ["foo", "bar"]},
        {"en": "foo"},
        {"en": ["bar"]},
    )
    assert score == 2 + 1  # foo→label +2, bar→alias +1
