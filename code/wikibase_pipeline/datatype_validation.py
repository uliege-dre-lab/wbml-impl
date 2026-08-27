from datetime import date

from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from .utils.verbose_utils import inform, warn

PROPERTY_VALUE_PREFIXES = ("urn:wikibase:property:", "urn:wikibase:propertyIRI:")
ITEM_VALUE_PREFIXES = ("urn:wikibase:item:", "urn:wikibase:itemIRI:")

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
    Input:
    - value: The RDFLib value to infer the Wikibase datatype from.
    Output:
    - The inferred Wikibase datatype as a string, or None if it cannot be inferred.
    """

    if isinstance(value, URIRef):
        iri = str(value)
        if any(iri.startswith(p) for p in ITEM_VALUE_PREFIXES):
            return "wikibase-item"
        if any(iri.startswith(p) for p in PROPERTY_VALUE_PREFIXES):
            return "wikibase-property"
        return "url"

    if isinstance(value, Literal):
        if value.language:
            return "monolingualtext"
        if value.datatype:
            return XSD_TO_WIKIBASE.get(str(value.datatype))
        return None

    return None


def _coerce_missing_value_to_property_datatype(
    property_datatype: str,
    value: Literal,
) -> Literal | URIRef:
    """
    Coerce a plain Literal (no explicit datatype, no language tag) to match
    the expected property datatype.
    Inputs:
    - property_datatype: The expected Wikibase property datatype as a string.
    - value: The RDFLib Literal value to coerce.
    Output:
    - The coerced value as an RDFLib Literal or URIRef.
    """
    val_str = str(value).strip()

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
        if val_str.lstrip("+-").isdigit():
            return Literal(val_str, datatype=XSD.gYear)
        try:
            date.fromisoformat(val_str)
        except ValueError as err:
            raise ValueError(
                f"Cannot coerce '{val_str}' to time: not a valid date."
            ) from err
        return Literal(val_str, datatype=XSD.date)

    if property_datatype == "external-id":
        return Literal(val_str, datatype=XSD.string)

    raise ValueError(
        f"Cannot coerce '{val_str}' to property datatype '{property_datatype}'."
    )


def normalize_value_for_property(
    property_datatype: str,
    value: Literal | URIRef,
    default_language: str,
    verbose: int,
) -> Literal | URIRef | None:
    """
    Validate and coerce an RDF value to match the expected property datatype.
    Special handling:
    - string/external-id + language-tagged literal → strip language tag
    - monolingualtext + literal without language → add default language
    - monolingualtext + URIRef → incompatible
    - Any other datatype mismatch → None
    Inputs:
    - property_datatype: The expected Wikibase property datatype as a string.
    - value: The RDFLib value to validate and coerce.
    - default_language: The default language code to use for monolingualtext values.
    - verbose: Verbosity level for logging.
    Output:
    - The normalized value if valid, otherwise None.
    """
    if property_datatype in ("string", "external-id"):
        if isinstance(value, Literal) and value.language:
            warn(
                f"Value {value!r} has a language tag but property expects "
                f"'{property_datatype}'; removing language tag.",
                verbose,
            )
            return Literal(str(value), datatype=XSD.string)

    if property_datatype == "monolingualtext":
        if isinstance(value, Literal):
            if value.language:
                return value
            if value.datatype and str(value.datatype) not in (
                str(XSD.string),
                str(XSD.normalizedString),
            ):
                warn(
                    f"Value {value!r} has incompatible datatype for 'monolingualtext'; "
                    f"coercing to string with default language '{default_language}'.",
                    verbose,
                )
            return Literal(str(value), lang=default_language)
        warn(
            f"Value {value!r} (type '{value_to_wikibase_datatype(value)}') "
            f"is incompatible with property 'monolingualtext'; skipping.",
            verbose,
        )
        return None

    value_datatype = value_to_wikibase_datatype(value)

    if value_datatype is not None:
        if value_datatype != property_datatype:
            warn(
                f"Datatype mismatch: property expects '{property_datatype}', "
                f"but value {value!r} has datatype '{value_datatype}'; skipping.",
                verbose,
            )
            return None
        return value

    if not isinstance(value, Literal):
        warn(
            f"Value {value!r} has no explicit datatype and is not a Literal; "
            f"cannot coerce to '{property_datatype}'; skipping.",
            verbose,
        )
        return None

    try:
        normalized = _coerce_missing_value_to_property_datatype(
            property_datatype=property_datatype,
            value=value,
        )
    except ValueError as exc:
        warn(f"Value {value!r}: {exc}", verbose)
        return None

    inform(
        f"Value {value!r} had no explicit datatype; coerced to '{property_datatype}'.",
        verbose,
    )
    return normalized


def _time_to_wikibase(value: Literal) -> dict:
    """
    Convert an RDF date/time Literal to a Wikibase time snak dict.
    Inputs:
    - value: The RDFLib Literal with an XSD date/time datatype.
    Output:
    - A dict with keys "time", "precision", "timezone", "before", "after",
    and "calendarmodel".
    """
    dt_str = str(value)
    datatype_uri = str(value.datatype) if value.datatype else ""
    GREGORIAN_CALENDAR = "http://www.wikidata.org/entity/Q1985727"
    base = {"timezone": 0, "before": 0, "after": 0, "calendarmodel": GREGORIAN_CALENDAR}

    if datatype_uri == str(XSD.gYear):
        return {**base, "time": f"+{dt_str}-00-00T00:00:00Z", "precision": 9}

    if datatype_uri == str(XSD.gYearMonth):
        year, month = dt_str.split("-", 1)
        return {**base, "time": f"+{year}-{month}-00T00:00:00Z", "precision": 10}

    if datatype_uri == str(XSD.date):
        return {**base, "time": f"+{dt_str}T00:00:00Z", "precision": 11}

    if not dt_str.startswith(("+", "-")):
        dt_str = f"+{dt_str}"
    if "T" not in dt_str:
        dt_str += "T00:00:00Z"
    elif not dt_str.endswith("Z"):
        dt_str += "Z"
    return {**base, "time": dt_str, "precision": 11}


def rdf_value_to_wikibase_value(
    value: Literal | URIRef,
    property_datatype: str,
    lookup: dict,
    default_language: str,
) -> dict | str | None:
    """
    Convert a normalized RDF value to the Python object expected by the
    Wikibase API.
    Inputs:
    - value: The normalized value, as a Python type.
    - property_datatype: The datatype of the property to which the value belongs.
    - lookup: The Wikibase lookup dict.
    - default_language: The default language for monolingualtext values.
    Output:
    - The Python object expected by the Wikibase API.
    """
    if property_datatype == "wikibase-item":
        iri_str = str(value)
        qid = lookup.get("items", {}).get(iri_str)
        if qid is None:
            raise ValueError(
                f"wikibase-item value <{iri_str}> not found in lookup['items']."
            )
        return {"entity-type": "item", "id": qid}

    if property_datatype == "wikibase-property":
        iri_str = str(value)
        prop_entry = lookup.get("properties", {}).get(iri_str)
        if prop_entry is None:
            raise ValueError(
                f"wikibase-property value <{iri_str}> "
                f"not found in lookup['properties']."
            )
        return {"entity-type": "property", "id": prop_entry["id"]}

    result = str(value).strip()

    if property_datatype in ("string", "url", "external-id"):
        return result

    if property_datatype == "monolingualtext":
        lang = getattr(value, "language", None) or default_language
        return {"text": result, "language": lang}

    if property_datatype == "quantity":
        amount = result
        try:
            float(amount)
        except ValueError as err:
            raise ValueError(
                f"Cannot convert '{amount}' to quantity: not a number."
            ) from err
        if not amount.startswith(("+", "-")):
            amount = f"+{amount}"
        return {"amount": amount, "unit": "1"}

    if property_datatype == "time":
        return _time_to_wikibase(value)

    raise ValueError(
        f"Unsupported property datatype '{property_datatype}' for value conversion."
    )
