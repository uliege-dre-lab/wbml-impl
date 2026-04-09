from rdflib.namespace import OWL, RDF, RDFS

from ..utils.properties_utils import lookup_get, search_wikibase_properties
from ..utils.verbose_utils import inform, warn

BUILTIN_PROPERTY_PREFIX = {
    RDF.type: {
        "label": "instance of",
        "datatype": "wikibase-item",
    },
    RDFS.subClassOf: {
        "label": "subclass of",
        "datatype": "wikibase-item",
    },
    OWL.sameAs: {
        "label": "same as",
        "datatype": "url",
    },
}


def search_builtins_properties(lookup: dict, wikibase_api, verbose: int = 0) -> None:
    """
    Ensure every builtin property exists in lookup['properties'].

    For each builtin IRI:
    1. Check lookup — correct datatype → use it; wrong datatype → raise.
    2. Search Wikibase by label (English) filtered by datatype.
    3. Exactly one match → use it.
       Zero or multiple → create a new property.
    4. Store result in lookup.
    """
    lookup.setdefault("properties", {})

    for predicate, spec in BUILTIN_PROPERTY_PREFIX.items():
        iri_str = str(predicate)
        label = spec["label"]
        expected_datatype = spec["datatype"]

        # Step 1: check lookup
        pid = lookup_get(lookup, iri_str, expected_datatype, wikibase_api)
        if pid is not None:
            inform(
                f"Resolved builtin property <{iri_str}> from lookup -> {pid} "
                f"(datatype='{expected_datatype}')",
                verbose,
            )
            lookup["properties"][iri_str] = {"id": pid, "datatype": expected_datatype}
            continue

        # Step 2: search Wikibase
        pid = search_wikibase_properties(
            wikibase_api, {"en": label}, "en", expected_datatype
        )

        if pid is not None:
            inform(
                f"Found builtin property '{label}' in Wikibase -> {pid} "
                f"(datatype='{expected_datatype}')",
                verbose,
            )
        else:
            warn(
                f"Builtin property '{label}' not found in Wikibase, creating it.",
                verbose,
            )
            pid = wikibase_api.create_property(
                labels={"en": label}, datatype=expected_datatype
            )
            inform(
                f"Created builtin property '{label}' -> {pid} "
                f"(datatype='{expected_datatype}')",
                verbose,
            )

        lookup["properties"][iri_str] = {"id": pid, "datatype": expected_datatype}
