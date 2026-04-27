#!/bin/bash
# Usage:
#   ./update.sh                                      # uses the default mapping
#   ./update.sh data/mappings/wbml_notion.ttl        # explicit mapping file

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

MAPPING="${1:-data/mappings/wbml_notion.ttl}"

if [ ! -f "$MAPPING" ]; then
  echo "Error: mapping file not found: $MAPPING" >&2
  exit 1
fi

echo "Running pipeline with mapping: $MAPPING"
python scripts/run_pipeline.py "$MAPPING"
