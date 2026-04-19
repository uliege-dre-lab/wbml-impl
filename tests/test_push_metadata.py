from unittest.mock import MagicMock

from wikibase_pipeline.resolver.instance_resolver import _push_instance_metadata
from wikibase_pipeline.resolver.schema_classes_resolver import _push_class_metadata
from wikibase_pipeline.resolver.schema_properties_resolver import (
    _push_property_metadata,
)


def make_api(existing_labels=None, existing_aliases=None, existing_descriptions=None):
    api = MagicMock()
    api.get_entity.return_value = {
        "labels": {lang: {"value": v} for lang, v in (existing_labels or {}).items()},
        "aliases": {
            lang: [{"value": v} for v in vals]
            for lang, vals in (existing_aliases or {}).items()
        },
        "descriptions": {
            lang: {"value": v} for lang, v in (existing_descriptions or {}).items()
        },
    }
    return api


def pushed_data(api):
    """Return the entity_data dict that was passed to edit_entity, or None."""
    if api.edit_entity.called:
        return api.edit_entity.call_args[0][1]
    return None


# ── Instance ────────────────────────────────────────────────────────────────────


class TestPushInstanceMetadata:
    def test_new_label_is_added(self):
        api = make_api()
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "cat"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        data = pushed_data(api)
        assert "labels" in data
        assert data["labels"]["en"]["value"] == "cat"

    def test_same_label_no_edit(self):
        api = make_api(existing_labels={"en": "cat"})
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "cat"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        assert not api.edit_entity.called

    def test_label_conflict_adds_as_alias(self):
        api = make_api(existing_labels={"en": "cat"})
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "kitty"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        data = pushed_data(api)
        assert "aliases" in data
        alias_values = [e["value"] for e in data["aliases"]["en"]]
        assert "kitty" in alias_values
        assert "labels" not in data  # original label not overwritten

    def test_label_conflict_overwrite_mode(self):
        api = make_api(existing_labels={"en": "cat"})
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "kitty"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
            overwrite_on_conflict=True,
        )
        data = pushed_data(api)
        assert data["labels"]["en"]["value"] == "kitty"

    def test_new_alias_added(self):
        api = make_api(existing_labels={"en": "cat"})
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "cat"}, "aliases": {"en": ["kitty"]}, "descriptions": {}},
            api,
            verbose=0,
        )
        data = pushed_data(api)
        assert "aliases" in data
        assert any(e["value"] == "kitty" for e in data["aliases"]["en"])

    def test_alias_already_exists_as_alias_not_duplicated(self):
        api = make_api(
            existing_labels={"en": "cat"}, existing_aliases={"en": ["kitty"]}
        )
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "cat"}, "aliases": {"en": ["kitty"]}, "descriptions": {}},
            api,
            verbose=0,
        )
        assert not api.edit_entity.called

    def test_alias_same_as_existing_label_not_added(self):
        api = make_api(existing_labels={"en": "cat"})
        _push_instance_metadata(
            "Q1",
            {"labels": {"en": "cat"}, "aliases": {"en": ["cat"]}, "descriptions": {}},
            api,
            verbose=0,
        )
        assert not api.edit_entity.called

    def test_empty_lang_key_skipped(self):
        api = make_api()
        _push_instance_metadata(
            "Q1",
            {"labels": {"": "no-lang"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        assert not api.edit_entity.called


# ── Classes ─────────────────────────────────────────────────────────────────────


class TestPushClassMetadata:
    def test_label_conflict_adds_as_alias(self):
        api = make_api(existing_labels={"en": "Animal"})
        _push_class_metadata(
            "Q1",
            {"labels": {"en": "Creature"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        data = pushed_data(api)
        assert "aliases" in data
        assert any(e["value"] == "Creature" for e in data["aliases"]["en"])

    def test_alias_same_as_existing_label_not_added(self):
        api = make_api(existing_labels={"en": "Animal"})
        _push_class_metadata(
            "Q1",
            {
                "labels": {"en": "Animal"},
                "aliases": {"en": ["Animal"]},
                "descriptions": {},
            },
            api,
            verbose=0,
        )
        assert not api.edit_entity.called


# ── Properties ──────────────────────────────────────────────────────────────────


class TestPushPropertyMetadata:
    def test_label_conflict_adds_as_alias(self):
        api = make_api(existing_labels={"en": "name"})
        _push_property_metadata(
            "P1",
            {"labels": {"en": "label"}, "aliases": {}, "descriptions": {}},
            api,
            verbose=0,
        )
        data = pushed_data(api)
        assert "aliases" in data
        assert any(e["value"] == "label" for e in data["aliases"]["en"])

    def test_alias_same_as_existing_label_not_added(self):
        api = make_api(existing_labels={"en": "name"})
        _push_property_metadata(
            "P1",
            {"labels": {"en": "name"}, "aliases": {"en": ["name"]}, "descriptions": {}},
            api,
            verbose=0,
        )
        assert not api.edit_entity.called
