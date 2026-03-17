import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import OWL, RDF, RDFS, SKOS

from wikibase_pipeline.queries import (
    ALIAS_Q,
    BUILTINS_Q,
    DESCRIPTION_Q,
    LABEL_Q,
    build_direct_claims_query,
    build_items_query,
    build_qualifiers_query,
    build_references_query,
    build_statement_links_query,
    build_statement_values_query,
)


def normalize_ws(text: str) -> str:
    return " ".join(text.split())


@pytest.fixture
def graph():
    g = Graph()

    item_prefix = "urn:wikibase:Q:"
    property_prefix = "urn:wikibase:P:"
    statement_prefix = "urn:wikibase:S:"
    qualifier_prefix = "urn:wikibase:QP:"
    reference_prefix = "urn:wikibase:RP:"

    q1 = URIRef(item_prefix + "1")
    q2 = URIRef(item_prefix + "2")
    p1 = URIRef(property_prefix + "1")
    stmt = URIRef(statement_prefix + "1")
    qp = URIRef(qualifier_prefix + "1")
    rp = URIRef(reference_prefix + "1")

    g.add((q1, RDFS.label, Literal("Item one", lang="en")))
    g.add((q1, SKOS.altLabel, Literal("Alias one", lang="en")))
    g.add(
        (
            q1,
            URIRef("http://schema.org/description"),
            Literal("A description", lang="en"),
        )
    )

    g.add((q1, p1, q2))
    g.add((q1, p1, stmt))
    g.add((stmt, p1, Literal("value")))
    g.add((stmt, qp, Literal("qualifier")))
    g.add((stmt, rp, Literal("reference")))

    g.add((q1, RDF.type, q2))
    g.add((q2, RDFS.subClassOf, q1))
    g.add((q1, OWL.sameAs, q2))

    return g


# -------------------------
# Query string tests
# -------------------------


def test_label_query_structure():
    q = normalize_ws(LABEL_Q)
    assert "SELECT ?s ?label ?lang" in q
    assert "?s <http://www.w3.org/2000/01/rdf-schema#label> ?label ." in q
    assert "BIND(LANG(?label) AS ?lang)" in q


def test_alias_query_structure():
    q = normalize_ws(ALIAS_Q)
    assert "SELECT ?s ?alias ?lang" in q
    assert "?s ?p ?alias ." in q
    assert "http://www.w3.org/2004/02/skos/core#altLabel" in q
    assert "http://schema.org/alternateName" in q
    assert "https://schema.org/alternateName" in q


def test_description_query_structure():
    q = normalize_ws(DESCRIPTION_Q)
    assert "SELECT ?s ?description ?lang" in q
    assert "?s ?p ?description ." in q
    assert "http://schema.org/description" in q
    assert "https://schema.org/description" in q
    assert "http://www.w3.org/2000/01/rdf-schema#comment" in q


def test_builtins_query_structure():
    q = normalize_ws(BUILTINS_Q)
    assert "SELECT DISTINCT ?p" in q
    assert "http://www.w3.org/1999/02/22-rdf-syntax-ns#type" in q
    assert "http://www.w3.org/2000/01/rdf-schema#subClassOf" in q
    assert "http://www.w3.org/2002/07/owl#sameAs" in q


# -------------------------
# Query execution tests
# -------------------------


def test_label_query_execution(graph):
    results = list(graph.query(LABEL_Q))
    assert len(results) == 1
    s, label, lang = results[0]
    assert str(label) == "Item one"
    assert str(lang) == "en"


def test_alias_query_execution(graph):
    results = list(graph.query(ALIAS_Q))
    assert len(results) == 1
    assert str(results[0].alias) == "Alias one"


def test_description_query_execution(graph):
    results = list(graph.query(DESCRIPTION_Q))
    assert len(results) == 1
    assert "description" in str(results[0].description)


def test_builtins_query_execution(graph):
    results = list(graph.query(BUILTINS_Q))
    props = {str(r.p) for r in results}
    assert str(RDF.type) in props
    assert str(RDFS.subClassOf) in props
    assert str(OWL.sameAs) in props


def test_items_query_execution(graph):
    q = build_items_query("urn:wikibase:Q:")
    results = list(graph.query(q))
    values = {str(r.x) for r in results}
    assert "urn:wikibase:Q:1" in values
    assert "urn:wikibase:Q:2" in values


def test_direct_claims_query_execution(graph):
    q = build_direct_claims_query("urn:wikibase:Q:", "urn:wikibase:P:")
    results = list(graph.query(q))
    assert any(str(r.o) == "urn:wikibase:Q:2" for r in results)


def test_statement_links_query_execution(graph):
    q = build_statement_links_query(
        "urn:wikibase:Q:", "urn:wikibase:P:", "urn:wikibase:S:"
    )
    results = list(graph.query(q))
    assert len(results) == 1
    assert str(results[0].stmt).startswith("urn:wikibase:S:")


def test_statement_values_query_execution(graph):
    q = build_statement_values_query(
        "urn:wikibase:S:", "urn:wikibase:P:", "urn:wikibase:Q:"
    )
    results = list(graph.query(q))
    assert len(results) == 1
    assert str(results[0].value) == "value"


def test_qualifiers_query_execution(graph):
    q = build_qualifiers_query("urn:wikibase:S:", "urn:wikibase:QP:", "urn:wikibase:Q:")
    results = list(graph.query(q))
    assert len(results) == 1
    assert str(results[0].value) == "qualifier"


def test_references_query_execution(graph):
    q = build_references_query("urn:wikibase:S:", "urn:wikibase:RP:", "urn:wikibase:Q:")
    results = list(graph.query(q))
    assert len(results) == 1
    assert str(results[0].value) == "reference"
