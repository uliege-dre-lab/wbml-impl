#!/usr/bin/env bash
set -e

python -m wikibase_pipeline.cli2 \
  --pipeline config/pipeline.ini \
  --start 1519 \
  --end 3330
