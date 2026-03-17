from .metadata import pick_best_label, strip_namespace
from .queries import (
    build_items_query,
    build_main_properties_query,
    build_qualifier_properties_query,
    build_reference_properties_query,
)
from .utils import inform


def resolve_properties(
    g, lookup: dict, wikibase_api, prefixes: dict, verbose: int
) -> None:
    resolve_properties_for_query(
        g,
        build_main_properties_query(prefixes["property"]),
        lookup,
        "properties",
        wikibase_api,
        prefixes["property"],
        verbose,
    )
    resolve_properties_for_query(
        g,
        build_qualifier_properties_query(prefixes["qualifier"]),
        lookup,
        "qualifiers",
        wikibase_api,
        prefixes["qualifier"],
        verbose,
    )
    resolve_properties_for_query(
        g,
        build_reference_properties_query(prefixes["reference"]),
        lookup,
        "references",
        wikibase_api,
        prefixes["reference"],
        verbose,
    )


def resolve_properties_for_query(
    g,
    query,
    lookup: dict,
    section: str,
    wikibase_api,
    prefix: str,
    verbose: int,
) -> None:
    lookup.setdefault(section, {})

    property_iris = set()
    for row in g.query(query):
        property_iris.add(str(row.p))

    for iri in sorted(property_iris):
        if iri in lookup[section]:
            continue

        pid = resolve_property_iri(iri, wikibase_api, prefix, verbose)
        lookup[section][iri] = pid


def resolve_property_iri(iri: str, wikibase_api, prefix: str, verbose: int) -> str:
    suffix = strip_namespace(iri, prefix)

    if getattr(wikibase_api, "sparql_construct", None) is not None:
        pid = wikibase_api.find_property_by_external_iri(iri)
        if pid is not None:
            inform(f"Resolved property {iri} via SPARQL -> {pid}", verbose)
            return pid

    pid = wikibase_api.search_property_by_label(suffix)
    if pid is not None:
        inform(f"Resolved property {iri} by suffix '{suffix}' -> {pid}", verbose)
        return pid

    raise ValueError(
        f"Unresolved property {iri}. "
        "Property creation is disabled because this pipeline "
        "integrates datasets, not schema."
    )


def resolve_items(
    g, lookup: dict, metadata: dict, wikibase_api, prefixes: dict, verbose: int
) -> None:
    lookup.setdefault("items", {})

    query = build_items_query(prefixes["item"])
    item_iris = {str(row.x) for row in g.query(query)}

    for iri in sorted(item_iris):
        if iri in lookup["items"]:
            continue

        qid = resolve_item_iri(iri, metadata, wikibase_api, prefixes["item"], verbose)
        lookup["items"][iri] = qid


def resolve_item_iri(
    iri: str, metadata: dict, wikibase_api, prefix: str, verbose: int
) -> str:
    label = pick_best_label(iri, metadata)
    suffix = strip_namespace(iri, prefix)

    if getattr(wikibase_api, "sparql_construct", None) is not None:
        qid = wikibase_api.find_item_by_external_iri(iri)
        if qid is not None:
            inform(f"Resolved item {iri} via SPARQL -> {qid}", verbose)
            return qid

    if label:
        qid = wikibase_api.search_item_by_label(label)
        if qid is not None:
            inform(f"Resolved item {iri} by label '{label}' -> {qid}", verbose)
            return qid

    qid = wikibase_api.search_item_by_label(suffix)
    if qid is not None:
        inform(f"Resolved item {iri} by suffix '{suffix}' -> {qid}", verbose)
        return qid

    create_label = label or suffix
    qid = wikibase_api.create_item(label=create_label)
    return qid


def resolve_object(obj, lookup: dict):
    obj_str = str(obj)

    if hasattr(obj, "datatype") or hasattr(obj, "language"):
        return obj

    if obj_str in lookup["items"]:
        return lookup["items"][obj_str]

    return obj
