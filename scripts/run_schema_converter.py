from pathlib import Path

from wikibase_pipeline.wbml_to_rml import run_schema_queries

if __name__ == "__main__":
    run_schema_queries(
        source_file_path=Path("mappings/wbml_pokedex.ttl"),
        queries_dir=Path("src/wikibase_pipeline/sparql/Schema"),
        output_path=Path("data/output/schema_pokedex.ttl"),
        verbose=2,
    )
