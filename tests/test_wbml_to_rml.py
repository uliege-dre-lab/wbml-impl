from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import XSD

from wikibase_pipeline.wbml_to_rml import (
    WBINT,
    WBML,
    assign_ids,
    collect_subtree_triples,
    delete_wbml_blocks,
)

EX = Namespace("https://example.org/test#")


def test_collect_subtree_triples_collects_nested_blank_nodes():
    graph = Graph()

    root = BNode()
    child = BNode()
    grandchild = BNode()

    graph.add((root, EX.p1, child))
    graph.add((child, EX.p2, grandchild))
    graph.add((grandchild, EX.p3, Literal("value")))

    triples = collect_subtree_triples(graph, root)

    assert len(triples) == 3
    assert (root, EX.p1, child) in triples
    assert (child, EX.p2, grandchild) in triples
    assert (grandchild, EX.p3, Literal("value")) in triples


def test_delete_wbml_blocks_removes_wbml_triples_and_blank_node_subtree():
    graph = Graph()

    subject = EX.item
    block = BNode()
    nested = BNode()

    graph.add((subject, WBML.label, block))
    graph.add((block, EX.value, nested))
    graph.add((nested, EX.text, Literal("Bulbasaur")))

    graph.add((subject, EX.keep, Literal("keep me")))

    delete_wbml_blocks(graph, verbose=0)

    assert (subject, WBML.label, block) not in graph
    assert (block, EX.value, nested) not in graph
    assert (nested, EX.text, Literal("Bulbasaur")) not in graph

    assert (subject, EX.keep, Literal("keep me")) in graph


def test_assign_ids_adds_global_statement_ids_and_reference_ids():
    graph = Graph()

    tm = EX.triplesMap
    statement_1 = BNode()
    statement_2 = BNode()

    ref_1 = BNode()
    ref_2 = BNode()

    graph.add((tm, WBML.statementMap, statement_1))
    graph.add((tm, WBML.statementMap, statement_2))

    graph.add((statement_1, WBML.referenceMap, ref_1))
    graph.add((statement_1, WBML.referenceMap, ref_2))

    assign_ids(graph, verbose=0)

    stat_ids = list(graph.objects(statement_1, WBINT.statID)) + list(
        graph.objects(statement_2, WBINT.statID)
    )

    assert len(stat_ids) == 2
    assert Literal(1, datatype=XSD.integer) in stat_ids
    assert Literal(2, datatype=XSD.integer) in stat_ids

    assert (ref_1, WBINT.refId, Literal(1, datatype=XSD.integer)) in graph
    assert (ref_2, WBINT.refId, Literal(2, datatype=XSD.integer)) in graph


def test_assign_ids_reference_ids_restart_for_each_statement_map():
    graph = Graph()

    tm = EX.triplesMap
    statement_1 = BNode()
    statement_2 = BNode()

    ref_1 = BNode()
    ref_2 = BNode()

    graph.add((tm, WBML.statementMap, statement_1))
    graph.add((tm, WBML.statementMap, statement_2))

    graph.add((statement_1, WBML.referenceMap, ref_1))
    graph.add((statement_2, WBML.referenceMap, ref_2))

    assign_ids(graph, verbose=0)

    assert (ref_1, WBINT.refId, Literal(1, datatype=XSD.integer)) in graph
    assert (ref_2, WBINT.refId, Literal(1, datatype=XSD.integer)) in graph
