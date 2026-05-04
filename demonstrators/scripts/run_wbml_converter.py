from pathlib import Path

from wikibase_pipeline.wbml_to_rml import convert_wbml_to_rml

if __name__ == "__main__":
    convert_wbml_to_rml(
        mapping_file_path=Path("demonstrators/pokemon/mappings/wbml_pokemon.ttl"),
        output_file_path=Path(
            "demonstrators/pokemon/mappings/rml_pokemon_converted.ttl"
        ),
        verbose=2,
    )
