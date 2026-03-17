from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDFS, SKOS

from wikibase_pipeline.metadata import (
    collect_metadata,
    pick_best_label,
    strip_namespace,
)


def test_collect_entity_metadata_collects_labels_aliases_descriptions():
    g = Graph()

    q1 = URIRef("urn:wikibase:Q:1")
    q2 = URIRef("urn:wikibase:Q:2")

    g.add((q1, RDFS.label, Literal("Bulbasaur", lang="en")))
    g.add((q1, RDFS.label, Literal("Bulbizarre", lang="fr")))
    g.add((q1, SKOS.altLabel, Literal("Seed Pokémon", lang="en")))
    g.add(
        (
            q1,
            URIRef("http://schema.org/description"),
            Literal("A grass Pokémon", lang="en"),
        )
    )

    g.add((q2, RDFS.label, Literal("Charmander", lang="en")))
    g.add(
        (
            q2,
            URIRef("https://schema.org/alternateName"),
            Literal("Lizard Pokémon", lang="en"),
        )
    )
    g.add(
        (
            q2,
            URIRef("http://www.w3.org/2000/01/rdf-schema#comment"),
            Literal("A fire Pokémon", lang="en"),
        )
    )

    metadata = collect_metadata(g, language="en", verbose=0)

    assert metadata["urn:wikibase:Q:1"]["labels"]["en"] == "Bulbasaur"
    assert metadata["urn:wikibase:Q:1"]["labels"]["fr"] == "Bulbizarre"
    assert metadata["urn:wikibase:Q:1"]["aliases"]["en"] == ["Seed Pokémon"]
    assert metadata["urn:wikibase:Q:1"]["descriptions"]["en"] == "A grass Pokémon"

    assert metadata["urn:wikibase:Q:2"]["labels"]["en"] == "Charmander"
    assert metadata["urn:wikibase:Q:2"]["aliases"]["en"] == ["Lizard Pokémon"]
    assert metadata["urn:wikibase:Q:2"]["descriptions"]["en"] == "A fire Pokémon"


def test_collect_entity_metadata_uses_default_language_when_missing_lang():
    g = Graph()
    q1 = URIRef("urn:wikibase:Q:1")

    g.add((q1, RDFS.label, Literal("No language label")))
    g.add((q1, SKOS.altLabel, Literal("No language alias")))
    g.add(
        (
            q1,
            URIRef("http://schema.org/description"),
            Literal("No language description"),
        )
    )

    metadata = collect_metadata(g, language="fr", verbose=0)

    assert metadata["urn:wikibase:Q:1"]["labels"]["fr"] == "No language label"
    assert metadata["urn:wikibase:Q:1"]["aliases"]["fr"] == ["No language alias"]
    assert (
        metadata["urn:wikibase:Q:1"]["descriptions"]["fr"] == "No language description"
    )


def test_collect_entity_metadata_collects_multiple_aliases_same_language():
    g = Graph()
    q1 = URIRef("urn:wikibase:Q:1")

    g.add((q1, SKOS.altLabel, Literal("Alias 1", lang="en")))
    g.add(
        (q1, URIRef("http://schema.org/alternateName"), Literal("Alias 2", lang="en"))
    )

    metadata = collect_metadata(g, language="en", verbose=0)

    assert metadata["urn:wikibase:Q:1"]["aliases"]["en"] == ["Alias 1", "Alias 2"]


def test_collect_entity_metadata_returns_empty_dict_for_empty_graph():
    g = Graph()

    metadata = collect_metadata(g, language="en", verbose=0)

    assert dict(metadata) == {}


def test_pick_best_label_returns_preferred_language_first():
    metadata = {
        "urn:wikibase:Q:1": {
            "labels": {
                "fr": "Bulbizarre",
                "en": "Bulbasaur",
            }
        }
    }

    result = pick_best_label("urn:wikibase:Q:1", metadata, preferred_langs=("en", "fr"))
    assert result == "Bulbasaur"


def test_pick_best_label_returns_second_preferred_language_if_first_missing():
    metadata = {
        "urn:wikibase:Q:1": {
            "labels": {
                "fr": "Bulbizarre",
            }
        }
    }

    result = pick_best_label("urn:wikibase:Q:1", metadata, preferred_langs=("en", "fr"))
    assert result == "Bulbizarre"


def test_pick_best_label_returns_any_label_if_no_preferred_language_found():
    metadata = {
        "urn:wikibase:Q:1": {
            "labels": {
                "de": "Bisasam",
            }
        }
    }

    result = pick_best_label("urn:wikibase:Q:1", metadata, preferred_langs=("en", "fr"))
    assert result == "Bisasam"


def test_pick_best_label_returns_none_if_no_labels():
    metadata = {"urn:wikibase:Q:1": {"labels": {}}}

    result = pick_best_label("urn:wikibase:Q:1", metadata)
    assert result is None


def test_pick_best_label_returns_none_if_iri_missing():
    metadata = {}

    result = pick_best_label("urn:wikibase:Q:999", metadata)
    assert result is None


def test_strip_namespace_returns_suffix():
    iri = "urn:wikibase:Q:123"
    prefix = "urn:wikibase:Q:"

    result = strip_namespace(iri, prefix)

    assert result == "123"


def test_strip_namespace_returns_empty_string_when_iri_equals_prefix():
    iri = "urn:wikibase:Q:"
    prefix = "urn:wikibase:Q:"

    result = strip_namespace(iri, prefix)

    assert result == ""


def test_strip_namespace_raises_if_prefix_does_not_match():
    iri = "urn:wikibase:Q:123"
    prefix = "urn:wikibase:P:"

    try:
        strip_namespace(iri, prefix)
        raise AssertionError("Expected ValueError")
    except ValueError as e:
        assert "does not start with prefix" in str(e)
