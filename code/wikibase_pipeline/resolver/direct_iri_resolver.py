import re

from rdflib import Graph, URIRef

from ..utils.verbose_utils import inform
from ..wikibase_api import WikibaseAPI

ITEM_IRI_PREFIX = "urn:wikibase:itemIRI:"
PROPERTY_IRI_PREFIX = "urn:wikibase:propertyIRI:"
QUALIFIER_IRI_PREFIX = "urn:wikibase:qualifierIRI:"
REFERENCE_IRI_PREFIX = "urn:wikibase:referenceIRI:"

_ITEM_ID_RE = re.compile(r"^Q\d+$")
_PROPERTY_ID_RE = re.compile(r"^P\d+$")


def collect_direct_iris(
    data_graph: Graph,
) -> tuple[list[str], list[str]]:
    """
    Scan every node in the data graph.
    Input:
    - data_graph: The RDFLib Graph containing the data to be processed.
    Outputs:
      - sorted list of urn:wikibase:itemIRI:* strings
      - sorted list of property-like direct IRI strings
        (propertyIRI:*, qualifierIRI:*, referenceIRI:*)
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


def extract_pid(iri_str: str) -> str:
    """
    Extract the P-number suffix from any of the three property-like prefixes.
    Input:
    - iri_str: The IRI string to extract the PID from.
    Output:
    - The PID string (e.g., "P123") if the prefix is recognized.
    """
    for prefix in (PROPERTY_IRI_PREFIX, QUALIFIER_IRI_PREFIX, REFERENCE_IRI_PREFIX):
        if iri_str.startswith(prefix):
            return iri_str[len(prefix) :]
    raise ValueError(f"Unrecognised property direct IRI: {iri_str}")


def resolve_direct_iris(
    data_graph: Graph,
    lookup: dict,
    wikibase_api: WikibaseAPI,
    verbose: int,
) -> None:
    """
    Main entry point.
    Writes to the lookup cache valid QIDs and PIDs.
    Raises ValueError listing all problems found.
    Inputs:
    - data_graph: The RDFLib Graph containing the data to be processed.
    - lookup: The lookup cache dictionary to update with resolved IDs.
    - wikibase_api: An instance of the WikibaseAPI class.
    - verbose: Verbosity level for logging.
    """
    lookup.setdefault("items", {})
    lookup.setdefault("properties", {})

    item_iris, property_direct_iris = collect_direct_iris(data_graph)

    if not item_iris and not property_direct_iris:
        return

    inform(
        f"Resolving direct IRIs: {len(item_iris)} item(s), "
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
        suffix = extract_pid(iri_str)
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
        qid = iri_str[len(ITEM_IRI_PREFIX) :]
        if iri_str in lookup["items"]:
            inform(f"  Direct item {qid} already in lookup.", verbose)
            continue
        try:
            wikibase_api.get_entity(qid, props="labels")
            lookup["items"][iri_str] = qid
            inform(f"  Direct item {qid} found.", verbose)
        except RuntimeError as exc:
            existence_errors.append(
                f"  <{iri_str}>: {qid} does not exist in Wikibase. ({exc})"
            )

    seen_pids: dict[str, str] = {}

    for iri_str in property_direct_iris:
        pid = extract_pid(iri_str)
        lookup_key = PROPERTY_IRI_PREFIX + pid

        if lookup_key in lookup["properties"]:
            inform(f"  Direct property {pid} already in lookup.", verbose)
            seen_pids[pid] = lookup_key
            continue

        if pid in seen_pids:
            continue
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
            inform(f"  Direct property {pid} found (datatype='{datatype}').", verbose)
        except RuntimeError as exc:
            existence_errors.append(
                f"  <{iri_str}>: {pid} does not exist in Wikibase. ({exc})"
            )

    if existence_errors:
        raise ValueError(
            "Direct IRI existence check failed — these IDs were not found "
            "in your Wikibase instance:\n" + "\n".join(existence_errors)
        )
