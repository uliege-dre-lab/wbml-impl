from __future__ import annotations

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from .resolve import resolve_object
from .utils import inform, warn

STRICT_COMPATIBILITY = {
    "wikibase-item": {"wikibase-item"},
    "string": {"string"},
    "external-id": {"string"},
    "url": {"url"},
    "quantity": {"quantity"},
    "boolean": {"string"},
    "time": {"time"},
    "monolingualtext": {"monolingualtext"},
}


NUMERIC_XSD_TYPES = {
    XSD.integer,
    XSD.int,
    XSD.long,
    XSD.short,
    XSD.byte,
    XSD.unsignedLong,
    XSD.unsignedInt,
    XSD.unsignedShort,
    XSD.unsignedByte,
    XSD.positiveInteger,
    XSD.negativeInteger,
    XSD.nonPositiveInteger,
    XSD.nonNegativeInteger,
    XSD.decimal,
    XSD.float,
    XSD.double,
}

TIME_XSD_TYPES = {
    XSD.date,
    XSD.dateTime,
    XSD.time,
    XSD.gYear,
    XSD.gYearMonth,
    XSD.gMonth,
    XSD.gMonthDay,
    XSD.gDay,
}


def infer_object_kind(value, prefixes: dict[str, str], verbose) -> str:
    if isinstance(value, URIRef):
        value_str = str(value)
        if value_str.startswith(prefixes["item"]):
            return "wikibase-item"
        return "url"

    if isinstance(value, Literal):
        if value.language:
            return "monolingualtext"

        if value.datatype in NUMERIC_XSD_TYPES:
            return "quantity"

        if value.datatype == XSD.boolean:
            return "string"

        if value.datatype in TIME_XSD_TYPES:
            return "time"

        if value.datatype == XSD.anyURI:
            return "url"

        if value.datatype == XSD.string:
            return "string"

        if value.datatype is None:
            return "string"

        warn(
            "Unsupported datatype for literal: "
            + str(value.datatype)
            + ", defaulting to string",
            verbose,
        )
        return "string"

    if isinstance(value, str) and value.startswith("Q"):
        return "wikibase-item"

    warn(
        "Unsupported datatype for literal: "
        + str(value.datatype)
        + ", defaulting to string",
        verbose,
    )
    return "string"


def validate_value_against_property(
    property_pid: str, property_datatype: str, value, prefixes: dict[str, str], verbose
) -> None:
    value_kind = infer_object_kind(value, prefixes, verbose)

    allowed_kinds = STRICT_COMPATIBILITY.get(property_datatype)
    if allowed_kinds is None:
        raise ValueError(
            "Unsupported Wikibase datatype "
            f"'{property_datatype}' for property {property_pid}."
        )

    if value_kind not in allowed_kinds:
        raise ValueError(
            f"Datatype mismatch for property {property_pid}: "
            f"Wikibase expects '{property_datatype}', "
            f"but RDF value {value!r} has inferred kind '{value_kind}'."
        )


def validate_structures(
    structures: dict, lookup: dict, wikibase_api, prefixes: dict[str, str], verbose: int
) -> None:
    inform("Pre-validating direct claims...", verbose)
    for _, prop_iri, obj in structures["direct_claims"]:
        pid = lookup["properties"][prop_iri]
        value = resolve_object(obj, lookup)
        property_datatype = wikibase_api.get_property_datatype(pid)

        validate_value_against_property(
            pid, property_datatype, value, prefixes, verbose
        )

    inform("Pre-validating statement values...", verbose)
    for _, prop_iri, value in structures["statement_values"]:
        pid = lookup["properties"][prop_iri]
        resolved_value = resolve_object(value, lookup)
        property_datatype = wikibase_api.get_property_datatype(pid)

        validate_value_against_property(
            pid, property_datatype, resolved_value, prefixes, verbose
        )

    inform("Pre-validating qualifiers...", verbose)
    for _, qp_iri, value in structures["qualifiers"]:
        pid = lookup["qualifiers"][qp_iri]
        resolved_value = resolve_object(value, lookup)
        property_datatype = wikibase_api.get_property_datatype(pid)

        validate_value_against_property(
            pid, property_datatype, resolved_value, prefixes, verbose
        )

    inform("Pre-validating references...", verbose)
    for _, rp_iri, value in structures["references"]:
        pid = lookup["references"][rp_iri]
        resolved_value = resolve_object(value, lookup)
        property_datatype = wikibase_api.get_property_datatype(pid)

        validate_value_against_property(
            pid, property_datatype, resolved_value, prefixes, verbose
        )

    inform("Datatype pre-validation completed successfully.", verbose)
