from rdflib.namespace import OWL, RDF, RDFS

from .queries import BUILTINS_Q
from .utils import inform, warn

BUILTIN_PROPERTY_PREFIX = {
    RDF.type: {
        "lookup_key": "rdf:type",
        "label": "instance of",
        "datatype": "wikibase-item",
    },
    RDFS.subClassOf: {
        "lookup_key": "rdfs:subClassOf",
        "label": "subclass of",
        "datatype": "wikibase-item",
    },
    OWL.sameAs: {
        "lookup_key": "owl:sameAs",
        "label": "same as",
        "datatype": "url",
    },
}


def search_builtins_properties(g, lookup: dict, wikibase_api, verbose: int = 0) -> None:
    lookup.setdefault("builtins", {})
    lookup.setdefault("properties", {})

    for row in g.query(BUILTINS_Q):
        predicate = row.p
        spec = BUILTIN_PROPERTY_PREFIX[predicate]
        key = spec["lookup_key"]

        if key in lookup["builtins"]:
            continue

        inform(f"Searching required property {key}", verbose)

        pid = wikibase_api.search_property_by_label(spec["label"])

        if pid is None:
            warn(
                f"Required core property '{spec['label']}' not found, creating it.",
                verbose,
            )
            pid = wikibase_api.create_property(
                label=spec["label"],
                datatype=spec["datatype"],
            )

        lookup["builtins"][key] = pid
        lookup["properties"][str(predicate)] = pid
