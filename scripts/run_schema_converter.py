from pathlib import Path

from wikibase_pipeline.wbml_to_rml import run_schema_queries

if __name__ == "__main__":
    run_schema_queries(
        source_file_path=Path("data/mappings/wbml_notion.ttl"),
        output_file_path=Path("data/output/schema_notion.ttl"),
        verbose=2,
    )
