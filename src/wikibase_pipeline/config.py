import configparser
from pathlib import Path

from .utils import warn


def parse_bool(value: str | bool | None, default: bool, verbose: int) -> bool:
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    s = str(value).strip()

    if s.lower() in {"false", "0", "no", "off", "False", "FALSE", "F"}:
        return False
    if s.lower() in {"true", "1", "yes", "on", "True", "TRUE", "T"}:
        return True

    warn(f"Unknown boolean value: {value!r}. Defaulting to {default}.", verbose=verbose)
    return default


def as_int(val: str, *, key: str, section: str) -> int:
    try:
        return int(val.strip())
    except ValueError as e:
        raise ValueError(f"Invalid int for [{section}] {key}: {val!r}") from e


def load_config_ini(config_path: Path, verbose: int = 1) -> str:
    config_path = Path(config_path).resolve()
    project_root = Path.cwd()

    if not config_path.is_file():
        raise FileNotFoundError(f"File not found: {config_path}")

    config = configparser.ConfigParser(interpolation=None)
    config.read(config_path)

    data: dict[str, dict[str, str]] = {
        section: dict(config.items(section)) for section in config.sections()
    }

    if not data:
        raise ValueError(
            f"No sections found in config file: {config_path}\n\n"
            "Example:\n"
            "[CONFIGURATION]\n"
            "output_file = out.nt\n\n"
            "[DataSource1]\n"
            "mappings = mapping.ttl\n"
        )

    output_section = None
    output_value = None
    for section, kv in data.items():
        if "output_file" in kv and kv["output_file"].strip():
            output_section = section
            output_value = kv["output_file"].strip()
            break

    if output_section is None:
        raise ValueError(
            "No 'output_file' defined in the config file "
            "or it is empty. Add something like:\n\n"
            "[your-section]\n"
            "output_file = output.nt\n"
        )

    p = Path(output_value)
    if p.suffix.lower() != ".nt":
        original_value = output_value
        new_value = str(p.with_suffix(".nt"))

        data[output_section]["output_file"] = new_value
        output_value = new_value
        warn(
            f"Warning: 'output_file' value '{original_value}' does not end with '.nt'. "
            f"Automatically changed to '{new_value}'.",
            verbose=verbose,
        )

    mapping_section = None
    mappings_value = None
    for section, kv in data.items():
        if "mappings" in kv and kv["mappings"].strip():
            mapping_section = section
            mappings_value = kv["mappings"].strip()
            break

    if mapping_section is None:
        raise ValueError(
            "No 'mappings' defined in the config file (in any section) "
            "or it is empty. Add something like:\n\n"
            "[your-section]\n"
            "mappings = mapping.ttl\n"
        )

    mapping_path = Path(mappings_value)
    if not mapping_path.is_absolute():
        mapping_path = (project_root / mapping_path).resolve()
    else:
        mapping_path = mapping_path.resolve()

    if not mapping_path.is_file():
        raise FileNotFoundError(
            "Mapping file not found.\n\n"
            f"Config: {config_path}\n"
            f"Detected 'mappings' in section [{mapping_section}]: {mappings_value}\n"
            f"Resolved path: {mapping_path}\n\n"
            "Fix: check the filename/path, or use an absolute path."
        )

    return output_value


def load_pipeline_ini(pipeline_path: Path | str) -> dict[str, dict[str, object]]:
    pipeline_path = Path(pipeline_path).resolve()

    if not pipeline_path.is_file():
        raise FileNotFoundError(f"File not found: {pipeline_path}")

    config = configparser.ConfigParser(interpolation=None)
    config.read(pipeline_path)

    data: dict[str, dict[str, str]] = {
        section: dict(config.items(section)) for section in config.sections()
    }

    if not data:
        raise ValueError(
            f"No sections found in pipeline ini: {pipeline_path}\n\n"
            "Expected sections like:\n"
            "[wikibase]\n[urn]\n[cache]\n"
        )

    wb = data.get("wikibase", {})

    if "verbose" in wb and wb["verbose"].strip():
        verbose = as_int(wb["verbose"], key="verbose", section="wikibase")
    else:
        verbose = 1
        warn("Missing '[wikibase] verbose'. Defaulting to 1.", verbose)

    api_url = wb.get("api_url", "").strip()
    if not api_url:
        raise ValueError(
            "Missing required field: [wikibase] api_url\n\n"
            "Example:\n"
            "[wikibase]\n"
            "api_url = https://example.org/w/api.php\n"
        )

    language = wb.get("language", "").strip()
    if not language:
        language = "en"
        warn("Missing '[wikibase] language'. Defaulting to 'en'.", verbose)

    tls_raw = wb.get("tls_verify", "").strip()
    if not tls_raw:
        tls_verify = True
        warn("Missing '[wikibase] tls_verify'. Defaulting to True.", verbose)
    else:
        tls_verify = parse_bool(tls_raw, default=True, verbose=verbose)

    sparql_endpoint = wb.get("sparql_endpoint", "").strip()
    if not sparql_endpoint:
        sparql_endpoint = None
        warn(
            "Missing '[wikibase] sparql_endpoint'. SPARQL queries will be disabled.",
            verbose,
        )

    urn = data.get("prefix", {})

    item_prefix = urn.get("item", "").strip()
    if not item_prefix:
        item_prefix = "urn:wikibase:item:"
        warn("Missing '[prefix] item'. Defaulting to 'urn:wikibase:item:'.", verbose)

    property_prefix = urn.get("property", "").strip()
    if not property_prefix:
        property_prefix = "urn:wikibase:property:"
        warn(
            "Missing '[prefix] property'. Defaulting to 'urn:wikibase:property:'.",
            verbose,
        )

    statement_prefix = urn.get("statement", "").strip()
    if not statement_prefix:
        statement_prefix = "urn:wikibase:statement:"
        warn(
            "Missing '[prefix] statement'. Defaulting to 'urn:wikibase:statement:'.",
            verbose,
        )

    reference_prefix = urn.get("reference", "").strip()
    if not reference_prefix:
        reference_prefix = "urn:wikibase:reference:"
        warn(
            "Missing '[prefix] reference'. Defaulting to 'urn:wikibase:reference:'.",
            verbose,
        )

    qualifier_prefix = urn.get("qualifier", "").strip()
    if not qualifier_prefix:
        qualifier_prefix = "urn:wikibase:qualifier:"
        warn(
            "Missing '[prefix] qualifier'. Defaulting to 'urn:wikibase:qualifier:'.",
            verbose,
        )

    prefixes = {
        "item": item_prefix,
        "property": property_prefix,
        "statement": statement_prefix,
        "reference": reference_prefix,
        "qualifier": qualifier_prefix,
    }

    seen = {}
    for name, value in prefixes.items():
        if value in seen:
            raise ValueError(
                "Invalid prefix config: prefixes must all be distinct.\n\n"
                f"{seen[value]}_prefix={value!r}\n"
                f"{name}_prefix={value!r}"
            )
        seen[value] = name

    cache = data.get("cache", {})

    lookup_file_raw = cache.get("lookup_file", "").strip()
    if not lookup_file_raw:
        lookup_file_raw = "data/lookup/lookup.json"
        warn(
            "Missing '[cache] lookup_file'. Defaulting to 'data/lookup/lookup.json'.",
            verbose,
        )

    lookup_path = Path(lookup_file_raw)
    if not lookup_path.is_absolute():
        lookup_path = (pipeline_path.parent / lookup_path).resolve()
    else:
        lookup_path = lookup_path.resolve()

    store_raw = cache.get("store_file", "").strip()
    if not store_raw:
        store_file = False
        warn("Missing '[cache] store_file'. Defaulting to False.", verbose)
    else:
        store_file = parse_bool(store_raw, default=False, verbose=verbose)

    return {
        "wikibase": {
            "api_url": api_url,
            "sparql_endpoint": sparql_endpoint,
            "language": language,
            "tls_verify": tls_verify,
            "verbose": verbose,
        },
        "prefix": {
            "item": item_prefix,
            "property": property_prefix,
            "statement": statement_prefix,
            "qualifier": qualifier_prefix,
            "reference": reference_prefix,
        },
        "cache": {
            "lookup_file": str(lookup_path),
            "store_file": store_file,
        },
    }
