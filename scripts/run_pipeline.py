import sys

from wikibase_pipeline.pipeline import update

if __name__ == "__main__":
    mapping = sys.argv[1] if len(sys.argv) > 1 else "data/mappings/wbml_pokemon.ttl"
    update(mapping)
