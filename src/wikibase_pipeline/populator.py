from __future__ import annotations

from rdflib import Graph, Namespace, URIRef

from .datatype_validation import (
    normalize_value_for_property,
    rdf_value_to_wikibase_value,
)
from .utils.verbose_utils import inform, warn

WBML = Namespace("https://example.org/wbml#")


def _values_match(wikibase_value, existing_value, property_datatype: str) -> bool:
    """
    Compare the value we would send to Wikibase against a value already
    stored in a claim returned by wbgetentities (mainsnak.datavalue.value).
    """
    if property_datatype == "wikibase-item":
        return isinstance(existing_value, dict) and wikibase_value.get(
            "id"
        ) == existing_value.get("id")
    if property_datatype in ("string", "url"):
        return wikibase_value == existing_value
    if property_datatype == "monolingualtext":
        return (
            isinstance(existing_value, dict)
            and wikibase_value.get("text") == existing_value.get("text")
            and wikibase_value.get("language") == existing_value.get("language")
        )
    if property_datatype == "quantity":
        return isinstance(existing_value, dict) and wikibase_value.get(
            "amount"
        ) == existing_value.get("amount")
    if property_datatype == "time":
        return (
            isinstance(existing_value, dict)
            and wikibase_value.get("time") == existing_value.get("time")
            and wikibase_value.get("precision") == existing_value.get("precision")
        )
    return False


def _find_existing_claim_guid(
    claims_by_pid: dict,
    pid: str,
    wikibase_value,
    property_datatype: str,
) -> str | None:
    """Return the GUID of a matching existing claim, or None."""
    for claim in claims_by_pid.get(pid, []):
        if claim.get("mainsnak", {}).get("snaktype") != "value":
            continue
        existing_value = claim["mainsnak"].get("datavalue", {}).get("value")
        if _values_match(wikibase_value, existing_value, property_datatype):
            return claim["id"]
    return None


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
PROPERTY_IRI_PREFIX = "urn:wikibase:propertyIRI:"
QUALIFIER_IRI_PREFIX = "urn:wikibase:qualifierIRI:"
REFERENCE_IRI_PREFIX = "urn:wikibase:referenceIRI:"


def _push_statements(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int,
) -> list[str]:
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
    new_statement_iris: list[str] = []
    claims_cache: dict[str, dict] = {}

    for stmt_node in stmt_nodes:
        stmt_str = str(stmt_node)

        # subject
        subjects = list(data_graph.objects(stmt_node, STMT_SUBJECT))
        if len(subjects) != 1:
            warn(
                f"  <{stmt_str}>: expected 1 subject, got {len(subjects)}. Skipping.",
                verbose,
            )
            continue
        subject_iri_str = str(subjects[0])
        subject_qid = lookup.get("items", {}).get(subject_iri_str)
        if subject_qid is None:
            prop_entry = lookup.get("properties", {}).get(subject_iri_str)
            if prop_entry is not None:
                subject_qid = prop_entry["id"]
        if subject_qid is None:
            raise ValueError(
                f"Statement <{stmt_str}>: subject <{subject_iri_str}> "
                f"not found in lookup['items'] or lookup['properties']."
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

        prop_iri_str = str(properties[0])
        prop_entry = lookup.get("properties", {}).get(prop_iri_str)
        if prop_entry is None:
            if prop_iri_str.startswith(PROPERTY_PREFIX):
                reason = "undeclared wbml property — add wbml:propertyType to schema"
            else:
                reason = "external predicate not registered as builtin"

            warn(
                f"<{stmt_str}>: property <{prop_iri_str}> not found in lookup "
                f"({reason}). Skipping.",
                verbose,
            )
            continue

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

        normalized = normalize_value_for_property(
            property_datatype, values[0], language_resolver.language, verbose
        )
        if normalized is None:
            continue
        try:
            wikibase_value = rdf_value_to_wikibase_value(
                normalized, property_datatype, lookup, language_resolver.language
            )
        except ValueError as exc:
            warn(f"  <{stmt_str}>: skipping — {exc}", verbose)
            continue

        # rank
        ranks = list(data_graph.objects(stmt_node, WBML.rank))
        if len(ranks) == 0:
            rank = "normal"
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

        # check Wikibase for an existing identical claim
        if subject_qid not in claims_cache:
            try:
                claims_cache[subject_qid] = wikibase_api.get_entity_claims(subject_qid)
            except Exception as exc:
                warn(f"  Could not fetch claims for {subject_qid}: {exc}", verbose)
                claims_cache[subject_qid] = {}

        existing_guid = _find_existing_claim_guid(
            claims_cache[subject_qid], pid, wikibase_value, property_datatype
        )
        if existing_guid is not None:
            lookup["statements"][stmt_str] = existing_guid
            inform(
                f"  <{stmt_str}> already exists as {existing_guid}, skipping.", verbose
            )
            continue

        # push
        try:
            guid = wikibase_api.add_statement(
                subject_qid=subject_qid,
                property_pid=pid,
                value=wikibase_value,
                property_datatype=property_datatype,
                rank=rank,
            )
            lookup["statements"][stmt_str] = guid
            new_statement_iris.append(stmt_str)
            claims_cache[subject_qid].setdefault(pid, []).append(
                {
                    "id": guid,
                    "mainsnak": {
                        "snaktype": "value",
                        "datavalue": {"value": wikibase_value},
                    },
                }
            )
            added_count += 1
            inform(f"  <{stmt_str}> → {guid}", verbose)
        except Exception as exc:
            warn(f"  <{stmt_str}>: could not add statement: {exc}", verbose)

    inform(f"Finished pushing statements. Total added: {added_count}", verbose)
    return new_statement_iris


def _push_qualifiers(
    data_graph: Graph,
    lookup: dict,
    wikibase_api,
    language_resolver,
    verbose: int,
    new_statement_iris: list[str],
) -> None:
    """
    For every newly-created statement, find qualifier triples:
      <statement_iri> <urn:wikibase:qualifier:PropKey> value

    The qualifier predicate prefix is swapped to urn:wikibase:property:PropKey
    to look up the PID and datatype from lookup["properties"].
    Values are validated against the property datatype before pushing.
    """
    if not new_statement_iris:
        inform("  No new statements this run, skipping qualifier push.", verbose)
        return

    statements = lookup.get("statements", {})
    inform(
        f"Pushing qualifiers for {len(new_statement_iris)} new statement(s) …", verbose
    )
    added_count = 0

    for stmt_iri_str in new_statement_iris:
        guid = statements[stmt_iri_str]
        stmt_node = URIRef(stmt_iri_str)

        for pred, obj in data_graph.predicate_objects(stmt_node):
            pred_str = str(pred)
            if pred_str.startswith(QUALIFIER_PREFIX):
                prop_key = pred_str[len(QUALIFIER_PREFIX) :]
                prop_iri_str = PROPERTY_PREFIX + prop_key
            elif pred_str.startswith(QUALIFIER_IRI_PREFIX):
                prop_key = pred_str[len(QUALIFIER_IRI_PREFIX) :]
                prop_iri_str = PROPERTY_IRI_PREFIX + prop_key
            else:
                continue

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
                    default_language=language_resolver.language,
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
    new_statement_iris: list[str],
) -> None:
    """
    Discover reference nodes attached to newly-created statements via
    wbml:statementReference and register them in lookup["references"].

    lookup["references"][ref_iri_str] = None   → discovered, not yet created
    lookup["references"][ref_iri_str] = hash   → already pushed to Wikibase
    """
    lookup.setdefault("references", {})
    count = 0

    for stmt_iri_str in new_statement_iris:
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
            if pred_str.startswith(REFERENCE_PREFIX):
                prop_key = pred_str[len(REFERENCE_PREFIX) :]
                prop_iri_str = PROPERTY_PREFIX + prop_key
            elif pred_str.startswith(REFERENCE_IRI_PREFIX):
                prop_key = pred_str[len(REFERENCE_IRI_PREFIX) :]
                prop_iri_str = PROPERTY_IRI_PREFIX + prop_key
            else:
                continue

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
                    default_language=language_resolver.language,
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
    1. Main statement snaks     (wbml:Statement nodes)
    2. Qualifiers               (urn:wikibase:qualifier: triples)
    3. Reference node discovery (wbml:statementReference triples)
    4. Reference records        (urn:wikibase:reference: triples)
    """
    new_stmts = _push_statements(
        data_graph, lookup, wikibase_api, language_resolver, verbose
    )
    _push_qualifiers(
        data_graph, lookup, wikibase_api, language_resolver, verbose, new_stmts
    )
    _push_reference_nodes(data_graph, lookup, verbose, new_stmts)
    _push_reference_records(
        data_graph, lookup, wikibase_api, language_resolver, verbose
    )
