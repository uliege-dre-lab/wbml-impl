from rdflib import Graph
from rdflib.namespace import OWL, RDF, RDFS

from wikibase_pipeline.builtins_properties import search_builtins_properties


class FakeWikibaseAPI:
    def __init__(self, search_results=None, create_results=None):
        self.search_results = search_results or {}
        self.create_results = create_results or {}
        self.search_calls = []
        self.create_calls = []

    def search_property_by_label(self, label):
        self.search_calls.append(label)
        return self.search_results.get(label)

    def create_property(self, label, datatype):
        self.create_calls.append((label, datatype))
        return self.create_results[label]


def test_search_builtins_properties_finds_existing_properties():
    g = Graph()
    g.add(
        (
            "urn:s".replace("urn:s", None)
            if False
            else __import__("rdflib").URIRef("urn:s"),
            RDF.type,
            __import__("rdflib").URIRef("urn:o"),
        )
    )
    g.add(
        (
            __import__("rdflib").URIRef("urn:s"),
            RDFS.subClassOf,
            __import__("rdflib").URIRef("urn:o2"),
        )
    )
    g.add(
        (
            __import__("rdflib").URIRef("urn:s"),
            OWL.sameAs,
            __import__("rdflib").URIRef("urn:o3"),
        )
    )

    lookup = {}
    api = FakeWikibaseAPI(
        search_results={
            "instance of": "P1",
            "subclass of": "P2",
            "same as": "P3",
        }
    )

    search_builtins_properties(g, lookup, api, verbose=0)

    assert lookup["builtins"]["rdf:type"] == "P1"
    assert lookup["builtins"]["rdfs:subClassOf"] == "P2"
    assert lookup["builtins"]["owl:sameAs"] == "P3"

    assert lookup["properties"][RDF.type] == "P1"
    assert lookup["properties"][RDFS.subClassOf] == "P2"
    assert lookup["properties"][OWL.sameAs] == "P3"

    assert set(api.search_calls) == {"instance of", "subclass of", "same as"}
    assert api.create_calls == []


def test_search_builtins_properties_creates_missing_properties():
    from rdflib import URIRef

    g = Graph()
    g.add((URIRef("urn:s"), RDF.type, URIRef("urn:o")))
    g.add((URIRef("urn:s"), RDFS.subClassOf, URIRef("urn:o2")))
    g.add((URIRef("urn:s"), OWL.sameAs, URIRef("urn:o3")))

    lookup = {}
    api = FakeWikibaseAPI(
        search_results={
            "instance of": None,
            "subclass of": None,
            "same as": None,
        },
        create_results={
            "instance of": "P10",
            "subclass of": "P11",
            "same as": "P12",
        },
    )

    search_builtins_properties(g, lookup, api, verbose=0)

    assert lookup["builtins"]["rdf:type"] == "P10"
    assert lookup["builtins"]["rdfs:subClassOf"] == "P11"
    assert lookup["builtins"]["owl:sameAs"] == "P12"

    assert lookup["properties"][RDF.type] == "P10"
    assert lookup["properties"][RDFS.subClassOf] == "P11"
    assert lookup["properties"][OWL.sameAs] == "P12"

    assert set(api.create_calls) == {
        ("instance of", "wikibase-item"),
        ("subclass of", "wikibase-item"),
        ("same as", "url"),
    }


def test_search_builtins_properties_mixes_found_and_created():
    from rdflib import URIRef

    g = Graph()
    g.add((URIRef("urn:s"), RDF.type, URIRef("urn:o")))
    g.add((URIRef("urn:s"), RDFS.subClassOf, URIRef("urn:o2")))
    g.add((URIRef("urn:s"), OWL.sameAs, URIRef("urn:o3")))

    lookup = {}
    api = FakeWikibaseAPI(
        search_results={
            "instance of": "P1",
            "subclass of": None,
            "same as": "P3",
        },
        create_results={
            "subclass of": "P20",
        },
    )

    search_builtins_properties(g, lookup, api, verbose=0)

    assert lookup["builtins"]["rdf:type"] == "P1"
    assert lookup["builtins"]["rdfs:subClassOf"] == "P20"
    assert lookup["builtins"]["owl:sameAs"] == "P3"

    assert lookup["properties"][RDF.type] == "P1"
    assert lookup["properties"][RDFS.subClassOf] == "P20"
    assert lookup["properties"][OWL.sameAs] == "P3"

    assert api.create_calls == [("subclass of", "wikibase-item")]


def test_search_builtins_properties_skips_already_known_builtins():
    from rdflib import URIRef

    g = Graph()
    g.add((URIRef("urn:s"), RDF.type, URIRef("urn:o")))
    g.add((URIRef("urn:s"), RDFS.subClassOf, URIRef("urn:o2")))
    g.add((URIRef("urn:s"), OWL.sameAs, URIRef("urn:o3")))

    lookup = {
        "builtins": {
            "rdf:type": "P1",
            "rdfs:subClassOf": "P2",
            "owl:sameAs": "P3",
        },
        "properties": {},
    }
    api = FakeWikibaseAPI()

    search_builtins_properties(g, lookup, api, verbose=0)

    assert lookup["builtins"]["rdf:type"] == "P1"
    assert lookup["builtins"]["rdfs:subClassOf"] == "P2"
    assert lookup["builtins"]["owl:sameAs"] == "P3"

    assert lookup["properties"] == {}
    assert api.search_calls == []
    assert api.create_calls == []


def test_search_builtins_properties_initializes_lookup_sections():
    from rdflib import URIRef

    g = Graph()
    g.add((URIRef("urn:s"), RDF.type, URIRef("urn:o")))

    lookup = {}
    api = FakeWikibaseAPI(
        search_results={"instance of": "P1"},
    )

    search_builtins_properties(g, lookup, api, verbose=0)

    assert "builtins" in lookup
    assert "properties" in lookup
    assert lookup["builtins"]["rdf:type"] == "P1"
    assert lookup["properties"][RDF.type] == "P1"


def test_search_builtins_properties_only_processes_predicates_present_in_graph():
    from rdflib import URIRef

    g = Graph()
    g.add((URIRef("urn:s"), RDF.type, URIRef("urn:o")))

    lookup = {}
    api = FakeWikibaseAPI(
        search_results={"instance of": "P1"},
    )

    search_builtins_properties(g, lookup, api, verbose=0)

    assert lookup["builtins"] == {"rdf:type": "P1"}
    assert lookup["properties"] == {RDF.type: "P1"}
    assert api.search_calls == ["instance of"]
    assert api.create_calls == []
