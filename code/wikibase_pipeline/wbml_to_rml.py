from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import XSD

from .utils.verbose_utils import inform, warn

WBML = Namespace("https://example.org/wbml#")
WBINT = Namespace("https://example.org/wbint#")

RML_QUERIES_DIR = "code/wikibase_pipeline/sparql/RML"
SCHEMA_QUERIES_DIR = "code/wikibase_pipeline/sparql/Schema"


def collect_subtree_triples(graph: Graph, root: BNode) -> set[tuple]:
    """
    Collect all triples in the subtree rooted at the given node.
    Used to remove entire WBML blocks after conversion to RML.
    Inputs:
    - graph: the RDF graph to traverse
    - root: the starting node
    Output:
    - a set of triples (s, p, o) that are part of the subtree
    """
    to_visit = [root]
    visited = set()
    triples_to_remove = set()

    while to_visit:
        node = to_visit.pop()

        if node in visited:
            continue
        visited.add(node)

        for s, p, o in graph.triples((node, None, None)):
            triples_to_remove.add((s, p, o))

            if isinstance(o, BNode):
                to_visit.append(o)

    return triples_to_remove


def delete_wbml_blocks(graph: Graph) -> None:
    """
    Remove all triples related to WBML from the graph.
    Inputs:
    - graph: the RDF graph to modify
    """
    triples_to_remove = set()

    for s, p, o in graph:
        if str(p).startswith(str(WBML)):
            triples_to_remove.add((s, p, o))

            if isinstance(o, BNode):
                triples_to_remove.update(collect_subtree_triples(graph, o))

    for triple in triples_to_remove:
        graph.remove(triple)


def assign_ids(graph: Graph, verbose: int) -> None:
    """
    Assign unique integer IDs to statementMaps and referenceMaps in the graph.
    Inputs:
    - graph: the RDF graph to modify
    - verbose: verbosity level for logging
    """
    tm_to_poms: dict = {}
    for tm, _, pom in graph.triples((None, WBML.statementMap, None)):
        tm_to_poms.setdefault(tm, []).append(pom)

    global_stat_id = 0
    for _, poms in tm_to_poms.items():
        for pom in poms:
            global_stat_id += 1
            graph.add(
                (pom, WBINT.statID, Literal(global_stat_id, datatype=XSD.integer))
            )

    inform(f"Assigned wbint:statID to {global_stat_id} statementMaps", verbose)

    ref_total = 0
    all_poms = [pom for poms in tm_to_poms.values() for pom in poms]
    for pom in all_poms:
        ref_maps = [rm for _, _, rm in graph.triples((pom, WBML.referenceMap, None))]
        for j, rm in enumerate(ref_maps, start=1):
            graph.add((rm, WBINT.refId, Literal(j, datatype=XSD.integer)))
            ref_total += 1

    inform(f"Assigned wbint:refId to {ref_total} referenceMaps", verbose)


def convert_wbml_to_rml(
    mapping_file_path: str | Path,
    output_file_path: str | Path,
    verbose: int = 1,
) -> Path:
    """
    Main conversion function that takes a WBML mapping file,
    applies SPARQL CONSTRUCT queries to transform it into RML,
    and writes the output to a file.
    Inputs:
    - mapping_file_path: path to the input WBML mapping file
    - output_file_path: path where the resulting RML mapping file will be written
    - verbose: verbosity level for logging
    Output:
    - the path to the generated RML mapping file
    """
    mapping_file_path = Path(mapping_file_path)
    rml_queries_dir = Path(RML_QUERIES_DIR)
    output_file_path = Path(output_file_path)

    source_graph = Graph()
    source_graph.parse(mapping_file_path, format="turtle")
    assign_ids(source_graph, verbose)

    result_graph = Graph()

    for triple in source_graph:
        result_graph.add(triple)

    inform(f"Loaded source graph: {len(source_graph)} triples", verbose)

    query_files = sorted(rml_queries_dir.glob("*.rq"))
    for query_file in query_files:
        query_text = query_file.read_text(encoding="utf-8")
        result = source_graph.query(query_text)

        added = 0
        for triple in result.graph:
            before = len(result_graph)
            result_graph.add(triple)
            if len(result_graph) > before:
                added += 1
        if added > 0:
            inform(f"{query_file.name}: +{added} triples", verbose)
        else:
            inform(f"{query_file.name}: no triples added", verbose)

    delete_wbml_blocks(result_graph)
    len_after = len(result_graph)
    if len_after == 0:
        warn("Result graph is empty after removing WBML triples", verbose)
    else:
        inform(f"Final graph: {len_after} triples", verbose)

    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    result_graph.serialize(destination=str(output_file_path), format="turtle")

    return output_file_path


def run_schema_queries(
    source_file_path: str | Path,
    output_file_path: str | Path,
    verbose: int = 1,
) -> Path:
    """
    Execute SPARQL CONSTRUCT queries to generate schema-level RDF.
    Inputs:
    - source_file_path: path to the input mapping file
    - output_file_path: path to the file where the output will be written
    - verbose: verbosity level for logging
    Output:
    - the path to the generated schema RDF file
    """
    source_file_path = Path(source_file_path)
    schema_queries_dir = Path(SCHEMA_QUERIES_DIR)
    output_file_path = Path(output_file_path)

    source_graph = Graph()
    source_graph.parse(source_file_path, format="turtle")
    inform(f"Loaded source graph: {len(source_graph)} triples", verbose)

    result_graph = Graph()

    query_files = sorted(schema_queries_dir.glob("*.rq"))

    for query_file in query_files:
        query_text = query_file.read_text(encoding="utf-8")
        result = source_graph.query(query_text)

        added = 0
        for triple in result.graph:
            before = len(result_graph)
            result_graph.add(triple)
            if len(result_graph) > before:
                added += 1
        if added > 0:
            inform(f"{query_file.name}: +{added} triples", verbose)
        else:
            inform(f"{query_file.name}: no triples added", verbose)

    inform(f"Final graph: {len(result_graph)} triples", verbose)

    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    result_graph.serialize(destination=str(output_file_path), format="turtle")

    return output_file_path
