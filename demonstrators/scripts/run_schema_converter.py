from pathlib import Path

from wikibase_pipeline.wbml_to_rml import run_schema_queries

if __name__ == "__main__":
    run_schema_queries(
        source_file_path=Path("demonstrators/pokemon/mappings/wbml_pokemon.ttl"),
        output_file_path=Path("demonstrators/pokemon/output/schema_pokemon.ttl"),
        verbose=2,
    )
