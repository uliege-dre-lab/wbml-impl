from pathlib import Path

from rdflib import Graph

from .builtins_properties import search_builtins_properties
from .config import load_config_ini, load_pipeline_ini
from .datatype_validation import validate_structures
from .lookup_io import load_lookup, save_lookup
from .metadata import collect_metadata
from .populator import extract_structures, write_structures
from .resolve import resolve_items, resolve_properties
from .rml_executor import rml_execute, validate_nt_file
from .utils import inform, warn
from .wikibase_api import WikibaseAPI


def update(pipeline_ini: str | Path, config_ini: str | Path) -> None:
    pipeline = load_pipeline_ini(pipeline_ini)
    verbose = pipeline["wikibase"]["verbose"]

    output_value = load_config_ini(config_ini, verbose=verbose)
    nt_path = Path(output_value)
    rml_execute(config_ini, output_value, verbose=verbose)
    validate_nt_file(nt_path)

    wb_api = WikibaseAPI(pipeline["wikibase"])
    lookup = load_lookup(pipeline["cache"]["lookup_file"], verbose)

    inform(f"Parsing RDF graph from {nt_path}", verbose)
    g = Graph()
    g.parse(nt_path, format="nt")

    metadata = collect_metadata(g, pipeline["wikibase"]["language"], verbose)

    search_builtins_properties(g, lookup, wb_api, verbose)

    prefixes = pipeline["prefix"]
    resolve_properties(g, lookup, wb_api, prefixes, verbose)
    resolve_items(g, lookup, metadata, wb_api, prefixes, verbose)

    structures = extract_structures(g, prefixes, verbose)

    validate_structures(structures, lookup, wb_api, prefixes, verbose)

    write_structures(structures, lookup, wb_api, verbose)

    save_lookup(pipeline["wikibase"]["lookup_file"], lookup, verbose)


def delete(pipeline_ini: str | Path, start: int, end: int) -> None:
    pipeline = load_pipeline_ini(pipeline_ini)
    verbose = pipeline["wikibase"]["verbose"]
    wb_api = WikibaseAPI(pipeline["wikibase"])
    deleted, failed = wb_api.delete_items_range(start, end)
    warn(f"Failed to delete {len(failed)} entities", verbose)
