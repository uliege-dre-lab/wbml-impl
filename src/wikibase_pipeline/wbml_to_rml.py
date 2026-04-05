from pathlib import Path

from rdflib import BNode, Graph, Literal, Namespace
from rdflib.namespace import XSD

from .utils import inform, warn

WBML = Namespace("https://example.org/wbml#")


def collect_subtree_triples(graph: Graph, root) -> set[tuple]:
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


def delete_wbml_blocks(graph: Graph, verbose: int) -> None:
    triples_to_remove = set()

    for s, p, o in graph:
        if str(p).startswith(str(WBML)):
            triples_to_remove.add((s, p, o))

            # remove subtree if object is a blank node
            if isinstance(o, BNode):
                triples_to_remove.update(collect_subtree_triples(graph, o))

    for triple in triples_to_remove:
        graph.remove(triple)

    inform(f"Removed {len(triples_to_remove)} WBML-related triples", verbose)


def assign_ids(graph: Graph, verbose: int) -> None:
    # --- statID per tripleMap ---
    tm_to_poms: dict = {}
    for tm, _, pom in graph.triples((None, WBML.predicateObjectMap, None)):
        tm_to_poms.setdefault(tm, []).append(pom)

    stat_total = 0
    for _, poms in tm_to_poms.items():
        for i, pom in enumerate(poms, start=1):
            graph.add((pom, WBML.statID, Literal(i, datatype=XSD.integer)))
            stat_total += 1

    inform(f"Assigned wbml:statID to {stat_total} predicateObjectMaps", verbose)

    # --- refId per predicateObjectMap ---
    ref_total = 0
    all_poms = [pom for poms in tm_to_poms.values() for pom in poms]
    for pom in all_poms:
        ref_maps = [rm for _, _, rm in graph.triples((pom, WBML.referenceMap, None))]
        for j, rm in enumerate(ref_maps, start=1):
            graph.add((rm, WBML.refId, Literal(j, datatype=XSD.integer)))
            ref_total += 1

    inform(f"Assigned wbml:refId to {ref_total} referenceMaps", verbose)


def convert_wbml_to_rml(
    mapping_file_path: str | Path,
    queries_dir: str | Path,
    output_file_path: str | Path,
    input_format: str = "turtle",
    output_format: str = "turtle",
    verbose: int = 1,
) -> None:
    mapping_file_path = Path(mapping_file_path)
    queries_dir = Path(queries_dir)
    output_file_path = Path(output_file_path)

    source_graph = Graph()
    source_graph.parse(mapping_file_path, format=input_format)
    assign_ids(source_graph, verbose)

    result_graph = Graph()

    # 1. copy everything
    for triple in source_graph:
        result_graph.add(triple)

    inform(f"Loaded source graph: {len(source_graph)} triples", verbose)

    # 2. apply CONSTRUCT queries
    query_files = sorted(queries_dir.glob("*.rq"))
    inform(f"Queries: {[q.name for q in query_files]}", verbose)

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
            warn(f"{query_file.name}: no triples added", verbose)

    # 3. remove WBML
    delete_wbml_blocks(result_graph, verbose)
    len_after = len(result_graph)
    if len_after == 0:
        warn("Result graph is empty after removing WBML triples", verbose)
    else:
        inform(f"Final graph: {len_after} triples", verbose)

    output_file_path.parent.mkdir(parents=True, exist_ok=True)
    result_graph.serialize(destination=str(output_file_path), format=output_format)

    inform(f"Written to: {output_file_path}", verbose)


def run_schema_queries(
    source_file_path: str | Path,
    queries_dir: str | Path,
    output_folder: str | Path,
    output_name: str,
    input_format: str = "turtle",
    output_format: str = "turtle",
    verbose: int = 1,
) -> None:
    source_file_path = Path(source_file_path)
    queries_dir = Path(queries_dir)
    output_folder = Path(output_folder)
    output_file_path = output_folder / output_name

    source_graph = Graph()
    source_graph.parse(source_file_path, format=input_format)
    inform(f"Loaded source graph: {len(source_graph)} triples", verbose)

    result_graph = Graph()

    query_files = sorted(queries_dir.glob("*.rq"))
    inform(f"Queries: {[q.name for q in query_files]}", verbose)

    for query_file in query_files:
        query_text = query_file.read_text(encoding="utf-8")
        result = source_graph.query(query_text)

        added = 0
        for triple in result.graph:
            before = len(result_graph)
            result_graph.add(triple)
            if len(result_graph) > before:
                added += 1

        inform(f"{query_file.name}: +{added} triples", verbose)

    inform(f"Final graph: {len(result_graph)} triples", verbose)

    output_folder.mkdir(parents=True, exist_ok=True)
    result_graph.serialize(destination=str(output_file_path), format=output_format)
    inform(f"Written to: {output_file_path}", verbose)
