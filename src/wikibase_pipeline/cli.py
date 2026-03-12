import argparse
from pathlib import Path

from .pipeline import update


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Wikibase RDF pipeline")

    parser.add_argument(
        "--pipeline",
        required=True,
        help="Path to pipeline.ini",
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Path to morph-kgc config.ini",
    )

    args = parser.parse_args()

    update(
        pipeline_ini=Path(args.pipeline),
        config_ini=Path(args.config),
    )


if __name__ == "__main__":
    main()
