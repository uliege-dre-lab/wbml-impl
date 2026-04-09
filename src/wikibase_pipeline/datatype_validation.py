from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from .utils.verbose_utils import warn

ITEM_PREFIX = "urn:wikibase:item:"

XSD_TO_WIKIBASE: dict[str, str] = {
    str(XSD.integer): "quantity",
    str(XSD.int): "quantity",
    str(XSD.long): "quantity",
    str(XSD.short): "quantity",
    str(XSD.decimal): "quantity",
    str(XSD.float): "quantity",
    str(XSD.double): "quantity",
    str(XSD.string): "string",
    str(XSD.boolean): "string",
    str(XSD.anyURI): "url",
    str(XSD.date): "time",
    str(XSD.dateTime): "time",
    str(XSD.time): "time",
    str(XSD.gYear): "time",
    str(XSD.gYearMonth): "time",
}


def value_to_wikibase_datatype(value) -> str | None:
    """
    Infer the Wikibase datatype from an RDF value.
      URIRef with item prefix  -> "wikibase-item"
      Other URIRef             -> "url"
      Language-tagged Literal  -> "monolingualtext"
      Typed Literal            -> mapped via XSD_TO_WIKIBASE (None if unsupported type)
      Plain Literal            -> None (cannot be inferred)
    """
    if isinstance(value, URIRef):
        return "wikibase-item" if str(value).startswith(ITEM_PREFIX) else "url"

    if isinstance(value, Literal):
        if value.language:
            return "monolingualtext"
        if value.datatype:
            return XSD_TO_WIKIBASE.get(str(value.datatype))
        return None  # plain literal without datatype or language

    return None


def _coerce_missing_value_to_property_datatype(
    property_datatype: str,
    value: Literal,
) -> Literal | URIRef:
    """
    Coerce a plain Literal (no explicit datatype, no language tag) to match
    the expected property datatype.
    Raises ValueError if coercion is not possible.
    """
    val_str = str(value)

    if property_datatype == "string":
        return Literal(val_str, datatype=XSD.string)

    if property_datatype == "url":
        return URIRef(val_str)

    if property_datatype == "quantity":
        try:
            float(val_str)
        except ValueError as err:
            raise ValueError(
                f"Cannot coerce '{val_str}' to quantity: not a number."
            ) from err
        return Literal(val_str, datatype=XSD.decimal)

    if property_datatype == "time":
        # Best-effort: assume ISO date
        return Literal(val_str, datatype=XSD.date)

    if property_datatype == "monolingualtext":
        raise ValueError(
            f"Cannot coerce plain literal '{val_str}' to monolingualtext: "
            "a language tag is required."
        )

    raise ValueError(
        f"Cannot coerce '{val_str}' to property datatype '{property_datatype}'."
    )


def normalize_value_for_property(
    property_datatype: str,
    value,
    verbose: int,
):
    """
    Strict validation + limited coercion.
    - If the value has an explicit/inferable datatype, it must match exactly.
    - If missing, try to coerce using the property datatype.
    Returns the original or coerced value.
    """
    value_datatype = value_to_wikibase_datatype(value)

    if value_datatype is not None:
        if value_datatype != property_datatype:
            raise ValueError(
                f"Datatype mismatch: property expects '{property_datatype}', "
                f"but value {value!r} has datatype '{value_datatype}'."
            )
        return value

    try:
        normalized = _coerce_missing_value_to_property_datatype(
            property_datatype=property_datatype,
            value=value,
        )
    except ValueError as exc:
        raise ValueError(
            f"Value {value!r} has no explicit datatype and cannot be coerced "
            f"to property datatype '{property_datatype}'."
        ) from exc

    warn(
        f"Value {value!r} had no explicit datatype; coerced to match "
        f"property datatype '{property_datatype}'.",
        verbose,
    )
    return normalized


def _time_to_wikibase(value: Literal) -> dict:
    """
    Convert an RDF date/time Literal to a Wikibase time snak dict.
    Precision is inferred from the XSD datatype.
    """
    dt_str = str(value)
    datatype_uri = str(value.datatype) if value.datatype else ""
    CALENDAR = "http://www.wikidata.org/entity/Q1985727"
    base = {"timezone": 0, "before": 0, "after": 0, "calendarmodel": CALENDAR}

    if datatype_uri == str(XSD.gYear):
        return {**base, "time": f"+{dt_str}-00-00T00:00:00Z", "precision": 9}

    if datatype_uri == str(XSD.gYearMonth):
        year, month = dt_str.split("-", 1)
        return {**base, "time": f"+{year}-{month}-00T00:00:00Z", "precision": 10}

    if datatype_uri == str(XSD.date):
        return {**base, "time": f"+{dt_str}T00:00:00Z", "precision": 11}

    # xsd:dateTime / xsd:time / fallback — day precision as conservative default
    if not dt_str.startswith(("+", "-")):
        dt_str = f"+{dt_str}"
    if "T" not in dt_str:
        dt_str += "T00:00:00Z"
    elif not dt_str.endswith("Z"):
        dt_str += "Z"
    return {**base, "time": dt_str, "precision": 11}


def rdf_value_to_wikibase_value(
    value,
    property_datatype: str,
    lookup: dict,
    default_language: str,
):
    """
    Convert a normalized RDF value to the Python object expected by the
    Wikibase API (will be JSON-serialized by add_statement).

    Raises ValueError if the conversion is not possible.
    """
    if property_datatype == "wikibase-item":
        iri_str = str(value)
        qid = lookup.get("items", {}).get(iri_str)
        if qid is None:
            raise ValueError(
                f"wikibase-item value <{iri_str}> not found in lookup['items']."
            )
        return {"entity-type": "item", "id": qid}

    if property_datatype in ("string", "url"):
        return str(value)

    if property_datatype == "monolingualtext":
        lang = getattr(value, "language", None) or default_language
        return {"text": str(value), "language": lang}

    if property_datatype == "quantity":
        amount = str(value)
        if not amount.startswith(("+", "-")):
            amount = f"+{amount}"
        return {"amount": amount, "unit": "1"}

    if property_datatype == "time":
        return _time_to_wikibase(value)

    raise ValueError(
        f"Unsupported property datatype '{property_datatype}' for value conversion."
    )
