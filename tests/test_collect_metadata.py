from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from wikibase_pipeline.resolver.instance_resolver import _collect_instance_metadata
from wikibase_pipeline.resolver.language_resolver import LanguageResolver
from wikibase_pipeline.resolver.schema_classes_resolver import _collect_class_metadata
from wikibase_pipeline.resolver.schema_properties_resolver import (
    _collect_property_metadata,
)

ITEM = URIRef("urn:wikibase:item:TestItem")
PROP = URIRef("urn:wikibase:property:TestProp")
VALID_LANGS = ["en", "fr"]


def make_resolver(lang="en"):
    return LanguageResolver(language=lang, valid_languages=VALID_LANGS, verbose=0)


# ── Shared behavior tests (run for instances and classes, same logic) ──────────


class TestCollectInstanceMetadata:
    def test_simple_tagged_label(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "cat"}
        assert meta["aliases"] == {}

    def test_duplicate_tagged_labels_same_lang_second_becomes_alias(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        g.add((ITEM, RDFS.label, Literal("kitty", lang="en")))
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert len(meta["labels"]) == 1
        assert "en" in meta["labels"]
        assert "en" in meta["aliases"]
        # one value is the label, the other is in aliases
        all_values = {meta["labels"]["en"]} | set(meta["aliases"]["en"])
        assert all_values == {"cat", "kitty"}

    def test_tagged_wins_over_untagged_same_lang(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        g.add((ITEM, RDFS.label, Literal("kitty")))  # untagged → resolves to "en"
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"]["en"] == "cat"  # tagged wins
        assert "kitty" in meta["aliases"].get("en", [])

    def test_untagged_same_string_as_tagged_silently_skipped(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        g.add((ITEM, RDFS.label, Literal("cat")))  # same string, untagged
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"]["en"] == "cat"
        assert meta["aliases"].get("en", []) == []  # NOT added as alias

    def test_no_labels_alias_promoted_default_lang_first(self):
        g = Graph()
        g.add((ITEM, SKOS.altLabel, Literal("kitty", lang="en")))
        g.add((ITEM, SKOS.altLabel, Literal("chat", lang="fr")))
        meta = _collect_instance_metadata(g, ITEM, make_resolver("en"), verbose=0)
        assert meta["labels"].get("en") == "kitty"  # default lang alias promoted
        assert "kitty" not in meta["aliases"].get("en", [])

    def test_no_labels_no_aliases_iri_suffix_fallback(self):
        g = Graph()
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "TestItem"}

    def test_explicit_alias_stays_alias(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        g.add((ITEM, SKOS.altLabel, Literal("kitty", lang="en")))
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"]["en"] == "cat"
        assert "kitty" in meta["aliases"]["en"]

    def test_two_languages(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("cat", lang="en")))
        g.add((ITEM, RDFS.label, Literal("chat", lang="fr")))
        meta = _collect_instance_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "cat", "fr": "chat"}


class TestCollectClassMetadata:
    """Same label logic as instances — spot-check key behaviors."""

    def test_tagged_wins_over_untagged(self):
        g = Graph()
        g.add((ITEM, RDFS.label, Literal("Animal", lang="en")))
        g.add((ITEM, RDFS.label, Literal("Beast")))  # untagged
        meta = _collect_class_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"]["en"] == "Animal"
        assert "Beast" in meta["aliases"].get("en", [])

    def test_no_labels_iri_suffix_fallback(self):
        g = Graph()
        meta = _collect_class_metadata(g, ITEM, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "TestItem"}

    def test_subclass_of_collected(self):
        g = Graph()
        parent = URIRef("urn:wikibase:item:ParentClass")
        g.add((ITEM, RDFS.label, Literal("Child", lang="en")))
        g.add((ITEM, RDFS.subClassOf, parent))
        meta = _collect_class_metadata(g, ITEM, make_resolver(), verbose=0)
        assert str(parent) in meta["subclass_of"]


class TestCollectPropertyMetadata:
    def test_simple_tagged_label(self):
        g = Graph()
        g.add((PROP, RDFS.label, Literal("name", lang="en")))
        meta = _collect_property_metadata(g, PROP, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "name"}

    def test_tagged_wins_over_untagged(self):
        g = Graph()
        g.add((PROP, RDFS.label, Literal("name", lang="en")))
        g.add((PROP, RDFS.label, Literal("label")))  # untagged
        meta = _collect_property_metadata(g, PROP, make_resolver(), verbose=0)
        assert meta["labels"]["en"] == "name"
        assert "label" in meta["aliases"].get("en", [])

    def test_no_labels_alias_promoted(self):
        g = Graph()
        g.add((PROP, SKOS.altLabel, Literal("identifier", lang="en")))
        meta = _collect_property_metadata(g, PROP, make_resolver(), verbose=0)
        assert meta["labels"].get("en") == "identifier"

    def test_no_labels_no_aliases_iri_suffix_fallback(self):
        g = Graph()
        meta = _collect_property_metadata(g, PROP, make_resolver(), verbose=0)
        assert meta["labels"] == {"en": "TestProp"}
