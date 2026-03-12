from pathlib import Path

from .config import load_config_ini, load_pipeline_ini
from .rml_executor import rml_execute


def update(pipeline_ini: str | Path, config_ini: str | Path) -> None:
    pipeline = load_pipeline_ini(pipeline_ini)

    verbose = pipeline.get("wikibase", {}).get("verbose", 0)

    _, output_value = load_config_ini(config_ini, verbose=verbose)

    rml_execute(config_ini, output_value, verbose=verbose)
