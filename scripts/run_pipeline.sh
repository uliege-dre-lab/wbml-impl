#!/usr/bin/env bash
set -e

python -m wikibase_pipeline.cli \
  --pipeline config/pipeline.ini \
  --config config/config.ini
