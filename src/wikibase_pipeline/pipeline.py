from pathlib import Path

from .config import load_config_ini, load_pipeline_ini
from .rml_executor import rml_execute
from .wikibase_api import WikibaseAPI


def update(pipeline_ini: str | Path, config_ini: str | Path) -> None:
    pipeline = load_pipeline_ini(pipeline_ini)

    verbose = pipeline["wikibase"]["verbose"]

    output_value = load_config_ini(config_ini, verbose=verbose)

    rml_execute(config_ini, output_value, verbose=verbose)

    _ = WikibaseAPI(pipeline["wikibase"])
