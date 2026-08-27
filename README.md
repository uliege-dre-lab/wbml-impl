# Wikibase Mapping Language (WBML)

Declarative generation of Wikibase statements.

## Project Overview

The goal of this project is to design a **declarative pipeline** that generates Wikibase statements from structured data and inserts them into a Wikibase instance.

The pipeline handles:

- RDF generation from source data
- reconciliation of entities and properties with existing Wikibase entities
- creation of missing entities when necessary
- management of opaque IRIs through a lookup mechanism

The objective is to simplify and automate the process of integrating external data into Wikibase while preserving consistency with the existing knowledge graph.

## Project Structure

- `vocabulary/` — WBML ontology declaration (git submodule, [uliege-dre-lab/wbml](https://github.com/uliege-dre-lab/wbml))
- `code/`       — Pipeline source code and SPARQL queries
- `demonstrators/` — Example use cases with input data and mappings

## Prerequisites

### Getting the vocabulary submodule

The WBML vocabulary lives in a separate repository and is included here as a Git submodule. If you haven't cloned yet:

```
git clone --recurse-submodules <this-repo-url>
```

If you already cloned without that flag:

```
git submodule update --init --recursive
```

### General

This project requires **Python >= 3.10**.

The dependencies are defined in `pyproject.toml` and are installed automatically when installing the package.

To install the package, run:
```
pip install -e .
```

For development (including testing tools):
```
pip install -e .[dev]
```

### Wikibase

A Wikibase instance should be running. The following information is required:
- Wikibase API URL
- Wikibase credentials: username and password with sufficient rights to create and modify entities

You can start one locally with docker-compose using the provided `docker-compose.yml` file.
```
docker-compose up -d
```

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
| `SEARCH_WIKIBASE` | Whether to search Wikibase by label before creating a new entity (`yes`/`no`) | `yes` |
| `LOOKUP_FILE` | Path to the lookup JSON file | `data/lookup/lookup.json` |
| `STORE_FILE` | Whether to save the lookup after the run (`yes`/`no`) | `no` |
| `RML_MAPPING_PATH` | Output path for the converted RML mapping | `data/mappings/converted_mapping.ttl` |
| `SCHEMA_OUTPUT_PATH` | Output path for the schema Turtle file | `data/output/schema.ttl` |
| `RML_OUTPUT_PATH` | Output path for the generated RDF triples | `data/output/output.nt` |
| `NA_VALUES` | Comma-separated source values that Morph-KGC treats as NULL when generating RDF | `,nan,None,none,null,NULL` |

> **Note:** Wikibase does not allow:
> -  two _items_ to share the same label and description in a given language,
> - two _properties_ to share the same label (+ datatype) in a given language. 
>
> If this occurs, the pipeline reuses the existing entity instead of failing. This happens whether `SEARCH_WIKIBASE` is `yes` or `no`.

### Environment file

All parameters must be set in a `.env` file at the root of the repository. A template is provided in `.env.example`.

To create your environment file from the template, run:
```
cp .env.example .env
```

Then fill in the required values (if you are using the provided Wikibase set-up, the required values are already set). Optional variables can be left empty to use their defaults.

## Usage
If you are on Linux or macOS, first make the script executable:

```bash
chmod +x code/update.sh
```

Run the pipeline from the project root by passing your WBML mapping file:

```bash
sh code/update.sh path/to/your/mapping.ttl
```

For example, to run the Pokédex Demonstrator:

```bash
sh code/update.sh demonstrators/pokemon/mappings/wbml_pokemon.ttl
```
Then you can analyze intermediary results in `data/` (or your custom output folder, if you changed the default paths), and the final results in your Wikibase instance (http://localhost:8181/wiki/Special:RecentChanges with the provided docker-compose setup).

> **Note:** For the `notion` demonstrator, you may hit a character limit error.
> If you're using the provided docker-compose setup, you can fix this by increasing the label/description length limit:
>
> 1. Open `config/LocalSettings.php` (generated after your first `docker-compose up -d`)
> 2. Add the following line at the end of the file:
>    ```php
>    $wgWBRepoSettings['string-limits']['multilang']['length'] = 500;
>    ```
> 3. Restart the Wikibase containers:
>    ```
>    docker-compose restart wikibase wikibase-jobrunner
>    ```
## License
MIT — see [LICENSE](LICENSE).
