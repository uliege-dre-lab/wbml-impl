#!/bin/bash
# Usage: ./update.sh data/mappings/wbml_pokemon.ttl

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

MAPPING="${1:?Error: mapping file is required. Usage: ./update.sh <mapping.ttl>}"

if [ ! -f "$MAPPING" ]; then
  echo "Error: mapping file not found: $MAPPING" >&2
  exit 1
fi

echo "Running pipeline with mapping: $MAPPING"
python -m wikibase_pipeline "$MAPPING"
