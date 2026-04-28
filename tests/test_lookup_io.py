import json

import pytest

from wikibase_pipeline.lookup_io import (
    load_lookup,
    save_lookup,
    validate_lookup_cache,
)


def test_load_lookup_returns_empty_lookup_when_path_is_none():
    lookup = load_lookup(None, verbose=0)

    assert lookup == {
        "items": {},
        "properties": {},
        "statements": {},
        "references": {},
    }


def test_load_lookup_returns_empty_lookup_when_file_missing(tmp_path):
    missing_file = tmp_path / "missing_lookup.json"

    lookup = load_lookup(missing_file, verbose=0)

    assert lookup == {
        "items": {},
        "properties": {},
        "statements": {},
        "references": {},
    }


def test_load_lookup_loads_items_and_properties_and_resets_runtime_sections(tmp_path):
    lookup_file = tmp_path / "lookup.json"

    lookup_file.write_text(
        json.dumps(
            {
                "items": {"urn:item:A": "Q1"},
                "properties": {"urn:property:P": {"id": "P1", "datatype": "string"}},
                "statements": {"old": "should be removed"},
                "references": {"old": "should be removed"},
            }
        ),
        encoding="utf-8",
    )

    lookup = load_lookup(lookup_file, verbose=0)

    assert lookup["items"] == {"urn:item:A": "Q1"}
    assert lookup["properties"] == {
        "urn:property:P": {"id": "P1", "datatype": "string"}
    }
    assert lookup["statements"] == {}
    assert lookup["references"] == {}


def test_load_lookup_initializes_missing_items_and_properties(tmp_path):
    lookup_file = tmp_path / "lookup.json"

    lookup_file.write_text("{}", encoding="utf-8")

    lookup = load_lookup(lookup_file, verbose=0)

    assert lookup["items"] == {}
    assert lookup["properties"] == {}
    assert lookup["statements"] == {}
    assert lookup["references"] == {}


def test_save_lookup_writes_only_persistent_sections(tmp_path):
    lookup_file = tmp_path / "lookup.json"

    lookup = {
        "items": {"urn:item:A": "Q1"},
        "properties": {"urn:property:P": {"id": "P1"}},
        "statements": {"runtime": "not saved"},
        "references": {"runtime": "not saved"},
    }

    save_lookup(lookup_file, lookup, verbose=0)

    data = json.loads(lookup_file.read_text(encoding="utf-8"))

    assert data == {
        "items": {"urn:item:A": "Q1"},
        "properties": {"urn:property:P": {"id": "P1"}},
    }


def test_save_lookup_creates_parent_directories(tmp_path):
    lookup_file = tmp_path / "nested" / "folder" / "lookup.json"

    save_lookup(
        lookup_file,
        {"items": {}, "properties": {}},
        verbose=0,
    )

    assert lookup_file.exists()


def test_save_lookup_raises_if_items_is_not_dict(tmp_path):
    lookup_file = tmp_path / "lookup.json"

    lookup = {
        "items": [],
        "properties": {},
    }

    with pytest.raises(ValueError, match="section 'items' must be a dict"):
        save_lookup(lookup_file, lookup, verbose=0)


def test_save_lookup_raises_if_properties_is_not_dict(tmp_path):
    lookup_file = tmp_path / "lookup.json"

    lookup = {
        "items": {},
        "properties": [],
    }

    with pytest.raises(ValueError, match="section 'properties' must be a dict"):
        save_lookup(lookup_file, lookup, verbose=0)


class FakeWikibaseAPI:
    def __init__(self, existing_ids):
        self.existing_ids = set(existing_ids)
        self.called_with = None

    def filter_existing_ids(self, ids):
        self.called_with = set(ids)
        return self.existing_ids


def test_validate_lookup_cache_keeps_existing_ids():
    lookup = {
        "items": {"urn:item:A": "Q1"},
        "properties": {"urn:property:P": {"id": "P1"}},
    }

    wb_api = FakeWikibaseAPI(existing_ids={"Q1", "P1"})

    validate_lookup_cache(lookup, wb_api, verbose=0)

    assert lookup["items"] == {"urn:item:A": "Q1"}
    assert lookup["properties"] == {"urn:property:P": {"id": "P1"}}
    assert wb_api.called_with == {"Q1", "P1"}


def test_validate_lookup_cache_evicts_stale_ids():
    lookup = {
        "items": {
            "urn:item:A": "Q1",
            "urn:item:B": "Q2",
        },
        "properties": {
            "urn:property:P1": {"id": "P1"},
            "urn:property:P2": {"id": "P2"},
        },
    }

    wb_api = FakeWikibaseAPI(existing_ids={"Q1", "P2"})

    validate_lookup_cache(lookup, wb_api, verbose=0)

    assert lookup["items"] == {"urn:item:A": "Q1"}
    assert lookup["properties"] == {
        "urn:property:P2": {"id": "P2"},
    }


def test_validate_lookup_cache_does_nothing_when_no_cached_ids():
    lookup = {
        "items": {},
        "properties": {},
    }

    wb_api = FakeWikibaseAPI(existing_ids=set())

    validate_lookup_cache(lookup, wb_api, verbose=0)

    assert lookup == {
        "items": {},
        "properties": {},
    }
    assert wb_api.called_with is None
