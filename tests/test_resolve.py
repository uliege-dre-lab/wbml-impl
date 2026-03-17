import pytest
from rdflib import Graph, Literal, URIRef

from wikibase_pipeline.resolve import (
    resolve_item_iri,
    resolve_items,
    resolve_object,
    resolve_properties,
    resolve_property_iri,
)


class FakeWikibaseAPI:
    def __init__(
        self,
        property_by_external_iri=None,
        property_by_label=None,
        item_by_external_iri=None,
        item_by_label=None,
        created_item_qid="Q999",
        sparql_construct=None,
    ):
        self.property_by_external_iri = property_by_external_iri or {}
        self.property_by_label = property_by_label or {}
        self.item_by_external_iri = item_by_external_iri or {}
        self.item_by_label = item_by_label or {}
        self.created_item_qid = created_item_qid
        self.sparql_construct = sparql_construct

        self.find_property_calls = []
        self.search_property_calls = []
        self.find_item_calls = []
        self.search_item_calls = []
        self.create_item_calls = []

    def find_property_by_external_iri(self, iri):
        self.find_property_calls.append(iri)
        return self.property_by_external_iri.get(iri)

    def search_property_by_label(self, label):
        self.search_property_calls.append(label)
        return self.property_by_label.get(label)

    def find_item_by_external_iri(self, iri):
        self.find_item_calls.append(iri)
        return self.item_by_external_iri.get(iri)

    def search_item_by_label(self, label):
        self.search_item_calls.append(label)
        return self.item_by_label.get(label)

    def create_item(self, label):
        self.create_item_calls.append(label)
        return self.created_item_qid


@pytest.fixture
def prefixes():
    return {
        "item": "urn:wikibase:Q:",
        "property": "urn:wikibase:P:",
        "qualifier": "urn:wikibase:QP:",
        "reference": "urn:wikibase:RP:",
    }


@pytest.fixture
def graph(prefixes):
    g = Graph()

    q1 = URIRef(prefixes["item"] + "Item1")
    q2 = URIRef(prefixes["item"] + "Item2")

    p1 = URIRef(prefixes["property"] + "Prop1")
    qp1 = URIRef(prefixes["qualifier"] + "Qual1")
    rp1 = URIRef(prefixes["reference"] + "Ref1")

    g.add((q1, p1, q2))
    g.add((q1, qp1, Literal("qualifier value")))
    g.add((q1, rp1, Literal("reference value")))

    return g


# -------------------------
# resolve_properties
# -------------------------


def test_resolve_properties_collects_all_property_kinds(graph, prefixes, monkeypatch):
    lookup = {}
    api = FakeWikibaseAPI()

    resolved = {
        prefixes["property"] + "Prop1": "P1",
        prefixes["qualifier"] + "Qual1": "P2",
        prefixes["reference"] + "Ref1": "P3",
    }

    def fake_resolve_property_iri(iri, wikibase_api, verbose):
        return resolved[iri]

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.resolve_property_iri",
        fake_resolve_property_iri,
    )

    resolve_properties(graph, lookup, api, prefixes, verbose=0)

    assert lookup["properties"] == {
        prefixes["property"] + "Prop1": "P1",
        prefixes["qualifier"] + "Qual1": "P2",
        prefixes["reference"] + "Ref1": "P3",
    }


def test_resolve_properties_skips_already_known_properties(
    graph, prefixes, monkeypatch
):
    lookup = {"properties": {prefixes["property"] + "Prop1": "P1"}}
    api = FakeWikibaseAPI()
    calls = []

    def fake_resolve_property_iri(iri, wikibase_api, verbose):
        calls.append(iri)
        return {
            prefixes["qualifier"] + "Qual1": "P2",
            prefixes["reference"] + "Ref1": "P3",
        }[iri]

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.resolve_property_iri",
        fake_resolve_property_iri,
    )

    resolve_properties(graph, lookup, api, prefixes, verbose=0)

    assert lookup["properties"] == {
        prefixes["property"] + "Prop1": "P1",
        prefixes["qualifier"] + "Qual1": "P2",
        prefixes["reference"] + "Ref1": "P3",
    }
    assert set(calls) == {
        prefixes["qualifier"] + "Qual1",
        prefixes["reference"] + "Ref1",
    }


# -------------------------
# resolve_property_iri
# -------------------------


def test_resolve_property_iri_raises_typeerror_for_bad_strip_namespace_call():
    api = FakeWikibaseAPI()

    with pytest.raises(TypeError):
        resolve_property_iri("urn:wikibase:P:Prop1", api, verbose=0)


# -------------------------
# resolve_items
# -------------------------


def test_resolve_items_current_code_raises_typeerror_because_wrong_call_signature(
    graph, prefixes
):
    lookup = {}
    metadata = {}
    api = FakeWikibaseAPI()

    with pytest.raises(TypeError):
        resolve_items(graph, lookup, metadata, api, prefixes, verbose=0)


# -------------------------
# resolve_item_iri
# -------------------------


def test_resolve_item_iri_resolves_via_sparql(monkeypatch):
    iri = "urn:wikibase:Q:Item1"
    metadata = {iri: {"labels": {"en": "Bulbasaur"}}}
    api = FakeWikibaseAPI(
        item_by_external_iri={iri: "Q1"},
        sparql_construct=object(),
    )

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.strip_namespace",
        lambda value: "Item1",
    )

    qid = resolve_item_iri(iri, metadata, api, verbose=0)

    assert qid == "Q1"
    assert api.find_item_calls == [iri]
    assert api.search_item_calls == []
    assert api.create_item_calls == []


def test_resolve_item_iri_resolves_by_label(monkeypatch):
    iri = "urn:wikibase:Q:Item1"
    metadata = {iri: {"labels": {"en": "Bulbasaur"}}}
    api = FakeWikibaseAPI(
        item_by_label={"Bulbasaur": "Q2"},
        sparql_construct=None,
    )

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.strip_namespace",
        lambda value: "Item1",
    )

    qid = resolve_item_iri(iri, metadata, api, verbose=0)

    assert qid == "Q2"
    assert api.search_item_calls == ["Bulbasaur"]
    assert api.create_item_calls == []


def test_resolve_item_iri_resolves_by_suffix_when_no_label_match(monkeypatch):
    iri = "urn:wikibase:Q:Item1"
    metadata = {}
    api = FakeWikibaseAPI(
        item_by_label={"Item1": "Q3"},
        sparql_construct=None,
    )

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.strip_namespace",
        lambda value: "Item1",
    )

    qid = resolve_item_iri(iri, metadata, api, verbose=0)

    assert qid == "Q3"
    assert api.search_item_calls == ["Item1"]
    assert api.create_item_calls == []


def test_resolve_item_iri_creates_item_with_label(monkeypatch):
    iri = "urn:wikibase:Q:Item1"
    metadata = {iri: {"labels": {"en": "Bulbasaur"}}}
    api = FakeWikibaseAPI(
        created_item_qid="Q10",
        sparql_construct=None,
    )

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.strip_namespace",
        lambda value: "Item1",
    )

    qid = resolve_item_iri(iri, metadata, api, verbose=0)

    assert qid == "Q10"
    assert api.create_item_calls == ["Bulbasaur"]


def test_resolve_item_iri_creates_item_with_suffix_when_no_label(monkeypatch):
    iri = "urn:wikibase:Q:Item1"
    metadata = {}
    api = FakeWikibaseAPI(
        created_item_qid="Q11",
        sparql_construct=None,
    )

    monkeypatch.setattr(
        "wikibase_pipeline.resolve.strip_namespace",
        lambda value: "Item1",
    )

    qid = resolve_item_iri(iri, metadata, api, verbose=0)

    assert qid == "Q11"
    assert api.create_item_calls == ["Item1"]


# -------------------------
# resolve_object
# -------------------------


def test_resolve_object_returns_literal_unchanged():
    lookup = {"items": {}}
    obj = Literal("hello")

    result = resolve_object(obj, lookup)

    assert result == obj


def test_resolve_object_resolves_known_item_iri():
    lookup = {"items": {"urn:wikibase:Q:1": "Q1"}}
    obj = URIRef("urn:wikibase:Q:1")

    result = resolve_object(obj, lookup)

    assert result == "Q1"


def test_resolve_object_returns_unknown_iri_unchanged():
    lookup = {"items": {}}
    obj = URIRef("urn:wikibase:Q:999")

    result = resolve_object(obj, lookup)

    assert result == obj
