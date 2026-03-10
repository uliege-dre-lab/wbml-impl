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


def load_config_ini(
    config_path: Path, verbose: int = 1
) -> tuple[dict[str, dict[str, str]], str]:
    config_path = Path(config_path).resolve()

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
        mapping_path = (config_path.parent / mapping_path).resolve()
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

    return data, output_value


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

    cmp_raw = wb.get("create_missing_properties", "").strip()
    if not cmp_raw:
        create_missing_properties = False
        warn(
            "Missing '[wikibase] create_missing_properties'. Defaulting to False.",
            verbose,
        )
    else:
        create_missing_properties = parse_bool(cmp_raw, default=False, verbose=verbose)

    sparql_endpoint = wb.get("sparql_endpoint", "").strip()
    if not sparql_endpoint:
        sparql_endpoint = None
        warn(
            "Missing '[wikibase] sparql_endpoint'. SPARQL queries will be disabled.",
            verbose,
        )

    urn = data.get("urn", {})

    item_prefix = urn.get("item_prefix", "").strip()
    if not item_prefix:
        item_prefix = "urn:wikibase:Q:"
        warn("Missing '[urn] item_prefix'. Defaulting to 'urn:wikibase:Q:'.", verbose)

    property_prefix = urn.get("property_prefix", "").strip()
    if not property_prefix:
        property_prefix = "urn:wikibase:P:"
        warn(
            "Missing '[urn] property_prefix'. Defaulting to 'urn:wikibase:P:'.", verbose
        )

    if item_prefix == property_prefix:
        raise ValueError(
            "Invalid urn config:"
            "item_prefix and property_prefix cannot be the same.\n\n"
            f"item_prefix={item_prefix!r}\n"
            f"property_prefix={property_prefix!r}"
        )

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
            "create_missing_properties": create_missing_properties,
            "verbose": verbose,
        },
        "urn": {
            "item_prefix": item_prefix,
            "property_prefix": property_prefix,
        },
        "cache": {
            "lookup_file": str(lookup_path),
            "store_file": store_file,
        },
    }
