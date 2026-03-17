import pytest
from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from wikibase_pipeline.datatype_validation import (
    infer_object_kind,
    validate_value_against_property,
)

PREFIXES = {
    "item": "urn:wikibase:item:",
    "property": "urn:wikibase:property:",
    "statement": "urn:wikibase:statement:",
    "qualifier": "urn:wikibase:qualifier:",
    "reference": "urn:wikibase:reference:",
}


def test_infer_object_kind_item():
    value = URIRef("urn:wikibase:item:Q1")
    assert infer_object_kind(value, PREFIXES, 0) == "wikibase-item"


def test_infer_object_kind_url():
    value = URIRef("http://example.org/x")
    assert infer_object_kind(value, PREFIXES, 0) == "url"


def test_infer_object_kind_quantity():
    value = Literal(42, datatype=XSD.integer)
    assert infer_object_kind(value, PREFIXES, 0) == "quantity"


def test_infer_object_kind_boolean():
    value = Literal(True, datatype=XSD.boolean)
    assert infer_object_kind(value, PREFIXES, 0) == "boolean"


def test_validate_value_against_property_ok():
    value = Literal("abc", datatype=XSD.string)
    validate_value_against_property(
        property_pid="P1",
        property_datatype="string",
        value=value,
        prefixes=PREFIXES,
        verbose=0,
    )


def test_validate_value_against_property_mismatch():
    value = Literal(42, datatype=XSD.integer)

    with pytest.raises(ValueError, match="Datatype mismatch"):
        validate_value_against_property(
            property_pid="P1",
            property_datatype="string",
            value=value,
            prefixes=PREFIXES,
            verbose=0,
        )
