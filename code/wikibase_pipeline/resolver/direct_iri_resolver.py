import re

from rdflib import Graph, URIRef

from ..utils.verbose_utils import inform

ITEM_IRI_PREFIX = "urn:wikibase:itemIRI:"
PROPERTY_IRI_PREFIX = "urn:wikibase:propertyIRI:"
QUALIFIER_IRI_PREFIX = "urn:wikibase:qualifierIRI:"
REFERENCE_IRI_PREFIX = "urn:wikibase:referenceIRI:"

_ITEM_ID_RE = re.compile(r"^Q\d+$")
_PROPERTY_ID_RE = re.compile(r"^P\d+$")


def _collect_direct_iris(
    data_graph: Graph,
) -> tuple[list[str], list[str]]:
    """
    Scan every node in the data graph.
    Returns:
      - sorted list of urn:wikibase:itemIRI:* strings
      - sorted list of property-like direct IRI strings
        (propertyIRI:*, qualifierIRI:*, referenceIRI:* — all P-number based)
    """
    item_iris: set[str] = set()
    property_direct_iris: set[str] = set()

    for s, p, o in data_graph:
        for node in (s, p, o):
            if not isinstance(node, URIRef):
                continue
            node_str = str(node)
            if node_str.startswith(ITEM_IRI_PREFIX):
                item_iris.add(node_str)
            elif (
                node_str.startswith(PROPERTY_IRI_PREFIX)
                or node_str.startswith(QUALIFIER_IRI_PREFIX)
                or node_str.startswith(REFERENCE_IRI_PREFIX)
            ):
                property_direct_iris.add(node_str)

    return sorted(item_iris), sorted(property_direct_iris)


def _extract_pid(iri_str: str) -> str:
    """Extract the P-number suffix from any of the three property-like prefixes."""
    for prefix in (PROPERTY_IRI_PREFIX, QUALIFIER_IRI_PREFIX, REFERENCE_IRI_PREFIX):
        if iri_str.startswith(prefix):
            return iri_str[len(prefix) :]
    raise ValueError(f"Unrecognised property direct IRI: {iri_str}")


def resolve_direct_iris(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    verbose: int = 1,
) -> None:
    """
    Main entry point.
    Raises ValueError listing all problems found
    and no data is written to Wikibase before this passes.
    """
    lookup.setdefault("items", {})
    lookup.setdefault("properties", {})

    item_iris, property_direct_iris = _collect_direct_iris(data_graph)

    if not item_iris and not property_direct_iris:
        return

    inform(
        f"Direct IRI resolver: {len(item_iris)} item(s), "
        f"{len(property_direct_iris)} property-like IRI(s) to verify.",
        verbose,
    )

    format_errors: list[str] = []

    for iri_str in item_iris:
        suffix = iri_str[len(ITEM_IRI_PREFIX) :]
        if not _ITEM_ID_RE.match(suffix):
            format_errors.append(
                f"  <{iri_str}>: '{suffix}' is not a valid item ID "
                f"(expected Q<digits>, e.g. Q155)."
            )

    for iri_str in property_direct_iris:
        suffix = _extract_pid(iri_str)
        if not _PROPERTY_ID_RE.match(suffix):
            format_errors.append(
                f"  <{iri_str}>: '{suffix}' is not a valid property ID "
                f"(expected P<digits>, e.g. P56)."
            )

    if format_errors:
        raise ValueError(
            "Direct IRI format validation failed — fix these "
            "wbml:classId / wbml:predicateId values before re-running:\n"
            + "\n".join(format_errors)
        )

    existence_errors: list[str] = []

    for iri_str in item_iris:
        if iri_str in lookup["items"]:
            inform(f"  Direct item <{iri_str}> already in lookup, skipping.", verbose)
            continue
        qid = iri_str[len(ITEM_IRI_PREFIX) :]
        inform(f"  Verifying direct item {qid} …", verbose)
        try:
            wikibase_api.get_entity(qid, props="labels")
            lookup["items"][iri_str] = qid
            inform(f"  OK — {qid} found.", verbose)
        except RuntimeError:
            existence_errors.append(f"  <{iri_str}>: {qid} does not exist in Wikibase.")

    seen_pids: dict[str, str] = {}  # pid → lookup key already stored

    for iri_str in property_direct_iris:
        pid = _extract_pid(iri_str)
        lookup_key = PROPERTY_IRI_PREFIX + pid

        if lookup_key in lookup["properties"]:
            inform(
                f"  Direct property {pid} already in lookup "
                f"(from <{iri_str}>), skipping.",
                verbose,
            )
            seen_pids[pid] = lookup_key
            continue

        if pid in seen_pids:
            inform(
                f"  Direct property {pid} already resolved "
                f"(from a previous IRI variant), skipping <{iri_str}>.",
                verbose,
            )
            continue

        inform(f"  Verifying direct property {pid} (from <{iri_str}>) …", verbose)
        try:
            entity = wikibase_api.get_entity(pid, props="datatype")
            datatype = entity.get("datatype")
            if not datatype:
                existence_errors.append(
                    f"  <{iri_str}>: {pid} found but returned no datatype."
                )
                continue
            lookup["properties"][lookup_key] = {"id": pid, "datatype": datatype}
            seen_pids[pid] = lookup_key
            inform(f"  OK — {pid} found (datatype='{datatype}').", verbose)
        except RuntimeError:
            existence_errors.append(f"  <{iri_str}>: {pid} does not exist in Wikibase.")

    if existence_errors:
        raise ValueError(
            "Direct IRI existence check failed — these IDs were not found "
            "in your Wikibase instance:\n" + "\n".join(existence_errors)
        )

    inform("Direct IRI resolution complete.", verbose)
