import sys

from .pipeline import update

if len(sys.argv) < 2:
    print("Error: mapping file is required.", file=sys.stderr)
    print("Usage: python -m wikibase_pipeline <mapping.ttl>", file=sys.stderr)
    sys.exit(1)

update(sys.argv[1])
