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
from .resolver.schema_properties_resolver import resolve_schema_properties
from .rml_executor import rml_execute, validate_nt_file
from .utils.verbose_utils import inform
from .wbml_to_rml import convert_wbml_to_rml, run_schema_queries
from .wikibase_api import WikibaseAPI


def update(mapping_file_path: str | Path) -> None:
    load_dotenv()
    cfg = load_env_config()

    mapping_file = Path(mapping_file_path)
    if not mapping_file.is_file():
        raise FileNotFoundError(f"Mapping file not found: {mapping_file_path}")

    rml_mapping = convert_wbml_to_rml(
        mapping_file,
        Path("src/wikibase_pipeline/sparql/rml"),
        Path(cfg["paths"]["rml_mapping"]),
        verbose=cfg["wikibase"]["verbose"],
    )
    rdf_schema = run_schema_queries(
        mapping_file,
        Path("src/wikibase_pipeline/sparql/schema"),
        Path(cfg["paths"]["schema_output"]),
        verbose=cfg["wikibase"]["verbose"],
    )

    output_value = str(Path(cfg["paths"]["rml_output"]).resolve())
    rml_execute(rml_mapping, output_value, verbose=cfg["wikibase"]["verbose"])
    validate_nt_file(output_value)

    lookup = load_lookup(cfg["cache"]["lookup_file"], cfg["wikibase"]["verbose"])
    wb_api = WikibaseAPI(cfg["wikibase"])
    validate_lookup_cache(lookup, wb_api, cfg["wikibase"]["verbose"])
    valid_languages = wb_api.get_valid_languages()
    language_resolver = LanguageResolver(
        cfg["wikibase"]["language"], valid_languages, verbose=cfg["wikibase"]["verbose"]
    )

    inform("Initialize basic schema metadata", cfg["wikibase"]["verbose"])
    g_schema = Graph()
    g_schema.parse(rdf_schema, format="turtle")

    search_builtins_properties(lookup, wb_api, cfg["wikibase"]["verbose"])
    resolve_schema_properties(
        g_schema, lookup, wb_api, language_resolver, cfg["wikibase"]["verbose"]
    )
    resolve_schema_classes(
        g_schema, lookup, wb_api, language_resolver, cfg["wikibase"]["verbose"]
    )

    g_objects = Graph()
    g_objects.parse(output_value, format="nt")

    inform(
        "Resolving direct Wikibase IDs (wbml:classId / wbml:predicateId)",
        cfg["wikibase"]["verbose"],
    )
    resolve_direct_iris(g_objects, lookup, wb_api, cfg["wikibase"]["verbose"])

    inform("Initialize instance metadata", cfg["wikibase"]["verbose"])
    resolve_instances(
        g_objects, lookup, wb_api, language_resolver, cfg["wikibase"]["verbose"]
    )

    inform("Pushing claims and statements to Wikibase", cfg["wikibase"]["verbose"])
    populate(g_objects, lookup, wb_api, language_resolver, cfg["wikibase"]["verbose"])

    if cfg["cache"]["store_file"]:
        save_lookup(cfg["cache"]["lookup_file"], lookup, cfg["wikibase"]["verbose"])
