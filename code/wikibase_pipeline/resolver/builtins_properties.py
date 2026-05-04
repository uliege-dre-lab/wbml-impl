from rdflib.namespace import RDF, RDFS

from ..utils.properties_utils import lookup_get, search_wikibase_properties
from ..utils.verbose_utils import inform
from ..wikibase_api import WikibaseAPI

BUILTIN_PROPERTY_PREFIX = {
    RDF.type: {
        "label": "instance of",
        "datatype": "wikibase-item",
    },
    RDFS.subClassOf: {
        "label": "subclass of",
        "datatype": "wikibase-item",
    },
}


def search_builtins_properties(
    lookup: dict, wikibase_api: WikibaseAPI, verbose: int = 0
) -> None:
    """
    Checks for the existence of built-in properties in the Wikibase instance
    and creates them if they do not exist.
    Inputs:
    - lookup: The lookup cache dictionary to store resolved properties.
    - wikibase_api: An instance of the WikibaseAPI class.
    - verbose: Verbosity level for logging.
    """
    lookup.setdefault("properties", {})

    for predicate, spec in BUILTIN_PROPERTY_PREFIX.items():
        iri_str = str(predicate)
        label = spec["label"]
        expected_datatype = spec["datatype"]

        pid = lookup_get(lookup, iri_str, expected_datatype, wikibase_api)
        if pid is not None:
            lookup["properties"][iri_str] = {"id": pid, "datatype": expected_datatype}
            continue

        pid = search_wikibase_properties(
            wikibase_api, {"en": label}, "en", expected_datatype
        )

        if pid is None:
            inform(
                f"Builtin property '{label}' not found in Wikibase, creating it.",
                verbose,
            )
            pid = wikibase_api.create_property(
                labels={"en": label}, datatype=expected_datatype
            )

        lookup["properties"][iri_str] = {"id": pid, "datatype": expected_datatype}
