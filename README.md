# ATFE9009 – Wikibase RDF Pipeline

Declarative generation of Wikibase statements.

## Project Overview

This project is developed as part of the Master's thesis in Engineering in Data Science.

The goal of this project is to design a **declarative pipeline** that generates Wikibase statements from structured data and inserts them into a Wikibase instance.

The pipeline handles:

- RDF generation from source data
- reconciliation of entities and properties with existing Wikibase entities
- creation of missing entities when necessary
- management of opaque IRIs through a lookup mechanism

The objective is to simplify and automate the process of integrating external data into Wikibase while preserving consistency with the existing knowledge graph.

## Prerequisites

### General

This project requires **Python >= 3.10**.

The dependencies are defined in `pyproject.toml` and are installed automatically when installing the package.

To install the package, run:
```
pip install .
```

For development (including testing tools):
```
pip install -e .[dev]
```

### Wikibase

A Wikibase instance should be running. The following information is required:
- Wikibase API URL
- Wikibase credentials: username and password with sufficient rights to create and modify entities

### Internal parameters

The pipeline behaviour is controlled by the following parameters:

| Variable | Description | Default |
|---|---|---|
| `API_URL` | Wikibase API URL | *(required)* |
| `WB_USER` | Wikibase username | *(required)* |
| `WB_PASSWORD` | Wikibase password | *(required)* |
| `VERBOSE` | Verbosity level: `0` (silent), `1` (normal), `2` (detailed) | `1` |
| `LANGUAGE` | Default language code used for labels | `en` |
| `TLS_VERIFY` | Whether to verify TLS certificates (`yes`/`no`) | `true` |
| `LOOKUP_FILE` | Path to the lookup JSON file | `data/lookup/lookup.json` |
| `STORE_FILE` | Whether to save the lookup after the run (`yes`/`no`) | `no` |
| `RML_MAPPING_PATH` | Output path for the converted RML mapping | `data/mappings/converted_mapping.ttl` |
| `SCHEMA_OUTPUT_PATH` | Output path for the schema Turtle file | `data/output/schema.ttl` |
| `RML_OUTPUT_PATH` | Output path for the generated RDF triples | `data/output/output.nt` |

### Environment file

All parameters must be set in a `.env` file at the root of the repository. A template is provided in `.env.example`.

To create your environment file from the template, run:
```
cp .env.example .env
```

Then fill in the required values. Optional variables can be left empty to use their defaults.

## Usage

Run the pipeline from the project root by passing your WBML mapping file:

```bash
sh scripts/update.sh mappings/wbml_mapping.ttl
```
