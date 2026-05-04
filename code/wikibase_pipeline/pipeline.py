from pathlib import Path

from dotenv import load_dotenv
from rdflib import Graph

from .config import load_env_config
from .lookup_io import load_lookup, save_lookup, validate_lookup_cache
from .populator import populate
from .resolver.builtins_properties import search_builtins_properties
from .resolver.direct_iri_resolver import resolve_direct_iris
from .resolver.instance_resolver import resolve_instances
from .resolver.language_resolver import LanguageResolver
from .resolver.schema_classes_resolver import resolve_schema_classes
from .resolver.schema_properties_resolver import (
    resolve_property_instances,
    resolve_schema_properties,
)
from .rml_executor import check_nt_line_prefixes, rml_execute
from .utils.verbose_utils import inform
from .wbml_to_rml import convert_wbml_to_rml, run_schema_queries
from .wikibase_api import WikibaseAPI


def update(mapping_file_path: str | Path) -> None:
    """
    Main function to run the Wikibase RDF pipeline.
    Input:
    - mapping_file_path: Path to the WBML mapping file.
    """

    load_dotenv()
    cfg = load_env_config()

    mapping_file = Path(mapping_file_path)
    if not mapping_file.is_file():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file_path}")

    verbose = cfg["wikibase"]["verbose"]

    inform("Converting WBML to RML...", verbose)
    rml_mapping = convert_wbml_to_rml(
        mapping_file,
        Path(cfg["paths"]["rml_mapping"]),
        verbose=verbose,
    )
    rdf_schema = run_schema_queries(
        mapping_file,
        Path(cfg["paths"]["schema_output"]),
        verbose=verbose,
    )

    inform("Executing RML mapping...", verbose)
    output_value = str(Path(cfg["paths"]["rml_output"]).resolve())
    rml_execute(rml_mapping, output_value, verbose=verbose)
    check_nt_line_prefixes(output_value)

    inform("Loading lookup cache...", verbose)
    lookup = load_lookup(cfg["cache"]["lookup_file"], verbose)

    inform("Wikibase API initialization", verbose)
    wb_api = WikibaseAPI(cfg["wikibase"])

    inform("Validating lookup cache...", verbose)
    validate_lookup_cache(lookup, wb_api, verbose)
    valid_languages = wb_api.get_valid_languages()
    language_resolver = LanguageResolver(cfg["wikibase"]["language"], valid_languages)
    inform("Initialize basic schema metadata", verbose)
    g_schema = Graph()
    g_schema.parse(rdf_schema, format="turtle")

    search_builtins_properties(lookup, wb_api, verbose)
    resolve_schema_properties(g_schema, lookup, wb_api, language_resolver, verbose)
    resolve_schema_classes(g_schema, lookup, wb_api, language_resolver, verbose)

    g_objects = Graph()
    g_objects.parse(output_value, format="nt")

    inform(
        "Resolving direct Wikibase IDs (wbml:classId / wbml:predicateId)",
        verbose,
    )
    resolve_direct_iris(g_objects, lookup, wb_api, verbose)

    inform("Initialize instance metadata", verbose)
    resolve_instances(g_objects, lookup, wb_api, language_resolver, verbose)
    resolve_property_instances(g_objects, lookup, wb_api, language_resolver, verbose)

    inform("Pushing claims and statements to Wikibase", verbose)
    populate(g_objects, lookup, wb_api, language_resolver, verbose)

    if cfg["cache"]["store_file"]:
        save_lookup(cfg["cache"]["lookup_file"], lookup, verbose)
        inform(f"Lookup cache saved to {cfg['cache']['lookup_file']}", verbose)
