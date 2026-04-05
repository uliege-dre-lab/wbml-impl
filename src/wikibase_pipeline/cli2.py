import argparse
from pathlib import Path

from .pipeline import delete


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Wikibase RDF pipeline")

    parser.add_argument(
        "--pipeline",
        required=True,
        help="Path to pipeline.ini",
    )

    parser.add_argument(
        "--start",
        required=True,
        help="QID to start from",
    )

    parser.add_argument(
        "--end",
        required=True,
        help="QID to end at",
    )

    args = parser.parse_args()

    delete(
        pipeline_ini=Path(args.pipeline),
        start=int(args.start),
        end=int(args.end),
    )


if __name__ == "__main__":
    main()
