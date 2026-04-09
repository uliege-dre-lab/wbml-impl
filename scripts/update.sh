#!/bin/sh
set -eu

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [ $# -lt 1 ]; then
    echo "Usage: sh scripts/update.sh <wbml_mapping.ttl>"
    exit 1
fi

MAPPING="$1"

cd "$PROJECT_ROOT"

python - << PYEOF
from wikibase_pipeline.pipeline import update
update("$MAPPING")
PYEOF
