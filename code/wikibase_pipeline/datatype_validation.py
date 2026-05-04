from rdflib import Literal, URIRef
from rdflib.namespace import XSD

from .utils.verbose_utils import warn

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
      Plain Literal            -> "string" (cannot be inferred)
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
        return "string"  # plain literal without datatype or language

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

    if property_datatype == "external-id":
        return Literal(val_str, datatype=XSD.string)

    raise ValueError(
        f"Cannot coerce '{val_str}' to property datatype '{property_datatype}'."
    )


def normalize_value_for_property(
    property_datatype: str,
    value,
    default_language: str,
    verbose: int,
):
    """
    Validate and coerce an RDF value to match the expected property datatype.
    Returns the corrected value on success, or None if the value should be skipped.
    warn() is called for all coercions and incompatibilities.

    Special handling:
    - string/external-id + language-tagged literal → strip language tag (warn)
    - monolingualtext + literal without language → add default language
      (warn if the original type was not a plain/xsd:string)
    - monolingualtext + URIRef → incompatible (warn + None)
    - Any other datatype mismatch → warn + None
    """
    # --- string / external-id: strip language tag if present
    if property_datatype in ("string", "external-id"):
        if isinstance(value, Literal) and value.language:
            warn(
                f"Value {value!r} has a language tag but property expects "
                f"'{property_datatype}'; removing language tag.",
                verbose,
            )
            return Literal(str(value), datatype=XSD.string)

    # --- monolingualtext: coerce anything without a language tag
    if property_datatype == "monolingualtext":
        if isinstance(value, Literal):
            if value.language:
                return value  # already correct
            # typed literal that is not a plain string → warn loudly
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
        # URIRef or other non-Literal
        warn(
            f"Value {value!r} (type '{value_to_wikibase_datatype(value)}') "
            f"is incompatible with property 'monolingualtext'; skipping.",
            verbose,
        )
        return None

    # --- standard path
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

    # --- plain literal with no datatype: attempt coercion
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
        warn(
            f"Value {value!r} cannot be coerced to '{property_datatype}':"
            f" {exc}; skipping.",
            verbose,
        )
        return None

    warn(
        f"Value {value!r} had no explicit datatype; coerced to '{property_datatype}'.",
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

    if property_datatype == "wikibase-property":
        iri_str = str(value)
        prop_entry = lookup.get("properties", {}).get(iri_str)
        if prop_entry is None:
            raise ValueError(
                f"wikibase-property value <{iri_str}> "
                f"not found in lookup['properties']."
            )
        return {"entity-type": "property", "id": prop_entry["id"]}

    if property_datatype in ("string", "url", "external-id"):
        result = str(value).strip()
        if result.lower() in {"none", "null", "nan"}:
            raise ValueError(f"Value is '{result}'; skipping.")
        return result

    if property_datatype == "monolingualtext":
        lang = getattr(value, "language", None) or default_language
        result = str(value).strip()
        if result.lower() in {"none", "null", "nan"}:
            raise ValueError(f"Value is '{result}'; skipping.")
        return {"text": result, "language": lang}

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
