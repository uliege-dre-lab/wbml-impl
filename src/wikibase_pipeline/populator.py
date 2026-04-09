from __future__ import annotations

from rdflib import Graph, Namespace, URIRef
from rdflib.namespace import RDF

from .datatype_validation import (
    normalize_value_for_property,
    rdf_value_to_wikibase_value,
)
from .utils.verbose_utils import inform, warn

WBML = Namespace("https://example.org/wbml#")

WBML_RANKS: dict[str, str] = {
    str(WBML.PreferredRank): "preferred",
    str(WBML.NormalRank): "normal",
    str(WBML.DeprecatedRank): "deprecated",
}

STMT_SUBJECT = WBML.statementSubject
STMT_PROPERTY = WBML.statementProperty
STMT_VALUE = WBML.statementValue

STATEMENT_PREFIX = "urn:wikibase:statement:"
QUALIFIER_PREFIX = "urn:wikibase:qualifier:"
PROPERTY_PREFIX = "urn:wikibase:property:"
REFERENCE_PREFIX = "urn:wikibase:reference:"


def _push_instance_of_claims(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    verbose: int,
) -> None:
    """
    For every rdf:type triple in the data graph, add an 'instance of' claim
    in Wikibase, provided both subject and object are in lookup["items"].
    """
    pid = lookup.get("properties", {}).get(str(RDF.type), {}).get("id")
    if pid is None:
        raise ValueError(
            "Cannot push 'instance of' claims: RDF.type PID not found in "
            "lookup['properties']."
        )

    inform(f"Pushing 'instance of' claims (pid={pid}) …", verbose)
    added_count = 0

    for subject, _, obj in data_graph.triples((None, RDF.type, None)):
        subject_str = str(subject)
        obj_str = str(obj)

        subject_qid = lookup["items"].get(subject_str)
        if subject_qid is None:
            raise ValueError(
                f"rdf:type triple <{subject_str}> rdf:type <{obj_str}>: "
                "subject not found in lookup['items']."
            )

        obj_qid = lookup["items"].get(obj_str)
        if obj_qid is None:
            raise ValueError(
                f"rdf:type triple <{subject_str}> rdf:type <{obj_str}>: "
                "object not found in lookup['items']."
            )

        try:
            wikibase_api.add_item_claim(
                subject_qid=subject_qid,
                property_pid=pid,
                value=obj_qid,
            )
            added_count += 1
        except Exception as exc:
            warn(f"  [{subject_qid}] Could not add 'instance of' claim: {exc}", verbose)

    inform(
        f"Finished pushing 'instance of' claims. Total added: {added_count}", verbose
    )


def _push_statements(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int,
) -> None:
    """
    For every statement node in the data graph:
      stmt wbml:StatementSubject  subject_iri
      stmt wbml:StatementProperty property_iri
      stmt wbml:StatementValue    value_rdf
      stmt wbml:rank              rank_iri    (optional, defaults to normal)

    Creates the main snak in Wikibase and stores the GUID in lookup["statements"].
    """
    lookup.setdefault("statements", {})

    stmt_nodes = sorted(
        node
        for node in data_graph.subjects(STMT_PROPERTY, None)
        if isinstance(node, URIRef) and str(node).startswith(STATEMENT_PREFIX)
    )
    added_count = 0

    for stmt_node in stmt_nodes:
        stmt_str = str(stmt_node)

        if stmt_str in lookup["statements"]:
            inform(f"  Statement <{stmt_str}> already in lookup, skipping.", verbose)
            continue

        # subject
        subjects = list(data_graph.objects(stmt_node, STMT_SUBJECT))
        if len(subjects) != 1:
            warn(
                f"  <{stmt_str}>: expected 1 subject, got {len(subjects)}. Skipping.",
                verbose,
            )
            continue
        subject_qid = lookup.get("items", {}).get(str(subjects[0]))
        if subject_qid is None:
            raise ValueError(
                f"Statement <{stmt_str}>: subject <{subjects[0]}> "
                f"not found in lookup['items']."
            )

        # property
        properties = list(data_graph.objects(stmt_node, STMT_PROPERTY))
        if len(properties) != 1:
            warn(
                f"  <{stmt_str}>: expected 1 property, got {len(properties)}. "
                f"Skipping.",
                verbose,
            )
            continue
        prop_entry = lookup.get("properties", {}).get(str(properties[0]))
        if prop_entry is None:
            raise ValueError(
                f"Statement <{stmt_str}>: property <{properties[0]}> "
                f"not found in lookup['properties']."
            )
        pid = prop_entry["id"]
        property_datatype = prop_entry.get("datatype")
        if not property_datatype:
            raise ValueError(
                f"Statement <{stmt_str}>: property <{properties[0]}> "
                f"has no datatype stored in lookup."
            )

        # value
        values = list(data_graph.objects(stmt_node, STMT_VALUE))
        if len(values) != 1:
            warn(
                f"  <{stmt_str}>: expected 1 value, got {len(values)}. Skipping.",
                verbose,
            )
            continue

        try:
            normalized = normalize_value_for_property(
                property_datatype=property_datatype,
                value=values[0],
                verbose=verbose,
            )
            wikibase_value = rdf_value_to_wikibase_value(
                normalized,
                property_datatype=property_datatype,
                lookup=lookup,
                default_language=language_resolver.language,
            )
        except ValueError as exc:
            warn(f"  <{stmt_str}>: skipping — {exc}", verbose)
            continue

        # rank
        ranks = list(data_graph.objects(stmt_node, WBML.rank))
        if len(ranks) == 0:
            rank = "normal"  # Wikibase default — wbsetrank not needed
        elif len(ranks) > 1:
            raise ValueError(
                f"Statement <{stmt_str}>: multiple ranks found: "
                f"{[str(r) for r in ranks]}."
            )
        else:
            rank = WBML_RANKS.get(str(ranks[0]))
            if rank is None:
                raise ValueError(
                    f"Statement <{stmt_str}>: unrecognized rank <{ranks[0]}>. "
                    f"Valid values: {list(WBML_RANKS)}."
                )

        # push
        try:
            guid = wikibase_api.add_statement(
                subject_qid=subject_qid,
                property_pid=pid,
                value=wikibase_value,
                property_datatype=property_datatype,  # ← new
                rank=rank,
            )
            lookup["statements"][stmt_str] = guid
            added_count += 1
            inform(f"  <{stmt_str}> → {guid}", verbose)
        except Exception as exc:
            warn(f"  <{stmt_str}>: could not add statement: {exc}", verbose)

    inform(f"Finished pushing statements. Total added: {added_count}", verbose)


def _push_qualifiers(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int,
) -> None:
    """
    For every statement in lookup["statements"], find qualifier triples:
      <statement_iri> <urn:wikibase:qualifier:PropKey> value

    The qualifier predicate prefix is swapped to urn:wikibase:property:PropKey
    to look up the PID and datatype from lookup["properties"].
    Values are validated against the property datatype before pushing.
    """
    statements = lookup.get("statements", {})
    if not statements:
        warn("  No statements in lookup, skipping qualifier push.", verbose)
        return

    inform(f"Pushing qualifiers for {len(statements)} statement(s) …", verbose)
    added_count = 0

    for stmt_iri_str, guid in statements.items():
        stmt_node = URIRef(stmt_iri_str)

        for pred, obj in data_graph.predicate_objects(stmt_node):
            pred_str = str(pred)
            if not pred_str.startswith(QUALIFIER_PREFIX):
                continue

            # property lookup
            prop_key = pred_str[len(QUALIFIER_PREFIX) :]
            prop_iri_str = PROPERTY_PREFIX + prop_key

            prop_entry = lookup.get("properties", {}).get(prop_iri_str)
            if prop_entry is None:
                warn(
                    f"  Qualifier <{pred_str}> on <{stmt_iri_str}>: "
                    f"property <{prop_iri_str}> not found in lookup['properties']. "
                    f"Skipping.",
                    verbose,
                )
                continue

            pid = prop_entry["id"]
            property_datatype = prop_entry.get("datatype")
            if not property_datatype:
                warn(
                    f"  Qualifier <{pred_str}> on <{stmt_iri_str}>: "
                    f"property has no datatype in lookup. Skipping.",
                    verbose,
                )
                continue

            # validate + convert value
            try:
                normalized = normalize_value_for_property(
                    property_datatype=property_datatype,
                    value=obj,
                    verbose=verbose,
                )
                wikibase_value = rdf_value_to_wikibase_value(
                    normalized,
                    property_datatype=property_datatype,
                    lookup=lookup,
                    default_language=language_resolver.language,
                )
            except ValueError as exc:
                warn(
                    f"  Qualifier <{pred_str}> on <{stmt_iri_str}>: skipping — {exc}",
                    verbose,
                )
                continue

            # push
            try:
                wikibase_api.add_qualifier(
                    claim_guid=guid,
                    property_pid=pid,
                    value=wikibase_value,
                )
                added_count += 1
                inform(
                    f"  [{guid}] Added qualifier {pid} = {wikibase_value!r}",
                    verbose,
                )
            except Exception as exc:
                warn(
                    f"  Qualifier <{pred_str}> on <{stmt_iri_str}>:"
                    f" could not add — {exc}",
                    verbose,
                )

    inform(f"Finished pushing qualifiers. Total added: {added_count}", verbose)


def _push_reference_nodes(
    data_graph: Graph,
    lookup: dict,
    verbose: int,
) -> None:
    """
    Discover all reference nodes attached to known statements via
    wbml:statementReference and register them in lookup["references"].

    lookup["references"][ref_iri_str] = None   → discovered, not yet created
    lookup["references"][ref_iri_str] = hash   → already pushed to Wikibase
    """
    lookup.setdefault("references", {})
    count = 0

    for stmt_iri_str in lookup.get("statements", {}):
        stmt_node = URIRef(stmt_iri_str)
        for ref_node in data_graph.objects(stmt_node, WBML.statementReference):
            ref_str = str(ref_node)
            if ref_str not in lookup["references"]:
                lookup["references"][ref_str] = None
                count += 1

    inform(f"Discovered {count} new reference node(s).", verbose)


def _push_reference_records(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int,
) -> None:
    """
    For each reference node registered in lookup["references"] that has not
    yet been pushed (hash is None):
      - find the parent statement GUID via wbml:statementReference
      - collect all <urn:wikibase:reference:PropKey> triples
      - validate each value against its property datatype
      - create the reference in Wikibase with all snaks at once
      - store the returned hash in lookup["references"]
    """
    pending = {
        ref_str
        for ref_str, ref_hash in lookup.get("references", {}).items()
        if ref_hash is None
    }
    if not pending:
        inform("  No pending reference nodes to push.", verbose)
        return

    inform(f"Pushing records for {len(pending)} reference node(s) …", verbose)
    added_count = 0

    for ref_str in pending:
        ref_node = URIRef(ref_str)

        # find parent statement GUID
        stmt_nodes = list(data_graph.subjects(WBML.statementReference, ref_node))
        if len(stmt_nodes) != 1:
            warn(
                f"  Reference <{ref_str}>: expected 1 parent statement, "
                f"got {len(stmt_nodes)}. Skipping.",
                verbose,
            )
            continue

        guid = lookup.get("statements", {}).get(str(stmt_nodes[0]))
        if guid is None:
            warn(
                f"  Reference <{ref_str}>: parent statement <{stmt_nodes[0]}> "
                "not found in lookup['statements']. Skipping.",
                verbose,
            )
            continue

        # collect + validate snaks ──
        snaks: list[tuple[str, any, str]] = []

        for pred, obj in data_graph.predicate_objects(ref_node):
            pred_str = str(pred)
            if not pred_str.startswith(REFERENCE_PREFIX):
                continue

            prop_key = pred_str[len(REFERENCE_PREFIX) :]
            prop_iri_str = PROPERTY_PREFIX + prop_key

            prop_entry = lookup.get("properties", {}).get(prop_iri_str)
            if prop_entry is None:
                warn(
                    f"  Reference record <{pred_str}> on <{ref_str}>: "
                    f"property <{prop_iri_str}> not found in lookup['properties']."
                    f" Skipping record.",
                    verbose,
                )
                continue

            pid = prop_entry["id"]
            property_datatype = prop_entry.get("datatype")
            if not property_datatype:
                warn(
                    f"  Reference record <{pred_str}> on <{ref_str}>: "
                    f"property has no datatype in lookup. Skipping record.",
                    verbose,
                )
                continue

            try:
                normalized = normalize_value_for_property(
                    property_datatype=property_datatype,
                    value=obj,
                    verbose=verbose,
                )
                wikibase_value = rdf_value_to_wikibase_value(
                    normalized,
                    property_datatype=property_datatype,
                    lookup=lookup,
                    default_language=language_resolver.language,
                )
            except ValueError as exc:
                warn(
                    f"  Reference record <{pred_str}> on <{ref_str}>: skipping — {exc}",
                    verbose,
                )
                continue

            snaks.append((pid, wikibase_value, property_datatype))

        if not snaks:
            warn(
                f"  Reference <{ref_str}>: no valid records collected. Skipping.",
                verbose,
            )
            continue

        # push to Wikibase
        try:
            ref_hash = wikibase_api.add_reference(guid, snaks)
            lookup["references"][ref_str] = ref_hash
            added_count += 1
            inform(f"  <{ref_str}> → hash={ref_hash}", verbose)
        except Exception as exc:
            warn(f"  Reference <{ref_str}>: could not create — {exc}", verbose)

    inform(f"Finished pushing reference records. Total created: {added_count}", verbose)


def populate(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int = 1,
) -> None:
    """
    Main entry point for populating Wikibase with claims and statements.
    1. 'instance of' claims     (rdf:type triples)
    2. Main statement snaks     (wbml:Statement nodes)
    3. Qualifiers               (urn:wikibase:qualifier: triples)
    4. Reference node discovery (wbml:statementReference triples)
    5. Reference records        (urn:wikibase:reference: triples)
    """
    _push_instance_of_claims(data_graph, lookup, wikibase_api, verbose)
    _push_statements(data_graph, lookup, wikibase_api, language_resolver, verbose)
    _push_qualifiers(data_graph, lookup, wikibase_api, language_resolver, verbose)
    _push_reference_nodes(data_graph, lookup, verbose)
    _push_reference_records(
        data_graph, lookup, wikibase_api, language_resolver, verbose
    )
