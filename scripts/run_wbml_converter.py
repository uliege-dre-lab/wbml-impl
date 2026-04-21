from pathlib import Path

from wikibase_pipeline.wbml_to_rml import convert_wbml_to_rml

if __name__ == "__main__":
    convert_wbml_to_rml(
        mapping_file_path=Path("data/mappings/wbml_pokemon.ttl"),
        queries_dir=Path("src/wikibase_pipeline/sparql/rml"),
        output_file_path=Path("data/mappings/rml_pokemon_converted.ttl"),
        verbose=2,
    )
