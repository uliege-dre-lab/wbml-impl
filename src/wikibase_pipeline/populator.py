from collections import defaultdict

from .queries import (
    build_direct_claims_query,
    build_qualifiers_query,
    build_references_query,
    build_statement_links_query,
    build_statement_values_query,
)
from .resolve import resolve_object
from .utils import inform


def extract_structures(g, prefixes: dict, verbose: int) -> dict:
    structures = {
        "direct_claims": [],
        "statement_links": [],
        "statement_values": [],
        "qualifiers": [],
        "references": [],
    }

    for row in g.query(
        build_direct_claims_query(prefixes["item"], prefixes["property"])
    ):
        structures["direct_claims"].append((str(row.s), str(row.p), row.o))

    for row in g.query(
        build_statement_links_query(
            prefixes["item"], prefixes["property"], prefixes["statement"]
        )
    ):
        structures["statement_links"].append(
            (str(row.item), str(row.prop), str(row.stmt))
        )

    for row in g.query(
        build_statement_values_query(
            prefixes["statement"], prefixes["property"], prefixes["item"]
        )
    ):
        structures["statement_values"].append((str(row.stmt), str(row.prop), row.value))

    for row in g.query(
        build_qualifiers_query(
            prefixes["statement"], prefixes["qualifier"], prefixes["item"]
        )
    ):
        structures["qualifiers"].append((str(row.stmt), str(row.qp), row.value))

    for row in g.query(
        build_references_query(
            prefixes["statement"], prefixes["reference"], prefixes["item"]
        )
    ):
        structures["references"].append((str(row.stmt), str(row.rp), row.value))

    inform("Extracted normalized statement structures.", verbose)
    return structures


def write_structures(structures: dict, lookup: dict, wikibase_api, verbose) -> None:
    statement_map = {}
    pending_statement_owner = {}

    inform("Adding direct claims...", verbose)
    for subj_iri, prop_iri, obj in structures["direct_claims"]:
        subj_qid = lookup["items"][subj_iri]
        pid = lookup["properties"][prop_iri]
        obj_value = resolve_object(obj, lookup)

        wikibase_api.add_claim(
            subject_qid=subj_qid,
            property_pid=pid,
            value=obj_value,
        )
    inform("Direct claims added.", verbose)

    inform("Adding statements...", verbose)
    for item_iri, prop_iri, stmt_iri in structures["statement_links"]:
        pending_statement_owner[stmt_iri] = {
            "subject_qid": lookup["items"][item_iri],
            "property_pid": lookup["properties"][prop_iri],
        }

    for stmt_iri, prop_iri, value in structures["statement_values"]:
        owner = pending_statement_owner[stmt_iri]
        pid = lookup["properties"][prop_iri]
        obj_value = resolve_object(value, lookup)

        statement_guid = wikibase_api.add_claim(
            subject_qid=owner["subject_qid"],
            property_pid=pid,
            value=obj_value,
        )
        statement_map[stmt_iri] = statement_guid
    inform("Statements added.", verbose)

    inform("Adding qualifiers...", verbose)
    for stmt_iri, qp_iri, value in structures["qualifiers"]:
        statement_guid = statement_map[stmt_iri]
        pid = lookup["qualifiers"][qp_iri]
        obj_value = resolve_object(value, lookup)

        wikibase_api.add_qualifier(
            statement_guid=statement_guid,
            property_pid=pid,
            value=obj_value,
        )
    inform("Qualifiers added.", verbose)

    inform("Adding references...", verbose)
    grouped_references = defaultdict(list)
    for stmt_iri, rp_iri, value in structures["references"]:
        grouped_references[stmt_iri].append((rp_iri, value))

    for stmt_iri, ref_triples in grouped_references.items():
        statement_guid = statement_map[stmt_iri]
        reference_snaks = []

        for rp_iri, value in ref_triples:
            pid = lookup["references"][rp_iri]
            obj_value = resolve_object(value, lookup)
            reference_snaks.append((pid, obj_value))

        wikibase_api.add_reference(
            statement_guid=statement_guid,
            reference_snaks=reference_snaks,
        )
    inform("References added.", verbose)
