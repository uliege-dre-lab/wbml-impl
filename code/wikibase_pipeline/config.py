import os
from pathlib import Path

from .utils.verbose_utils import inform, warn

_BOOL_TRUE = {"1", "t", "true", "yes", "on", "y"}
_BOOL_FALSE = {"0", "f", "false", "no", "off", "n"}


def parse_bool(value: str | None, *, key: str, default: bool | None = None) -> bool:
    """
    Parse an env var string into a bool.
    """
    if value is None or value.strip() == "":
        if default is not None:
            return default
        raise ValueError(
            f"Environment variable '{key}' is required but missing or empty."
        )

    s = value.strip().lower()
    if s in _BOOL_TRUE:
        return True
    if s in _BOOL_FALSE:
        return False

    raise ValueError(
        f"Cannot parse '{key}={value!r}' as a boolean.\n"
        f"Accepted values: {sorted(_BOOL_TRUE | _BOOL_FALSE)}"
    )


def require(key: str) -> str:
    """
    Read a mandatory env var. Raises EnvironmentError if absent or empty.
    """
    val = os.getenv(key, "").strip()
    if not val:
        raise OSError(
            f"Required environment variable '{key}' is not set or is empty.\n"
            f"Add it to your .env file:  {key}=<value>"
        )
    return val


def read_optional(key: str, default: str = "") -> str:
    """
    Read an optional env var, returning default if absent or empty.
    """
    val = os.getenv(key, "").strip()
    return val if val else default


def as_int(raw: str, *, key: str) -> int:
    """
    Parse an env var string into an int, with error handling.
    """
    try:
        return int(raw.strip())
    except ValueError as err:
        raise ValueError(
            f"Environment variable '{key}={raw!r}' must be an integer."
        ) from err


def resolve_path(path_str: str) -> Path:
    """
    Resolve a path to an absolute Path.
    """
    path = Path(path_str)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def ensure_suffix(path: Path, expected_suffix: str, *, key: str, verbose: int) -> Path:
    """
    Ensure the path has the expected suffix, replace it if not.
    """
    if path.suffix.lower() != expected_suffix.lower():
        original = str(path)
        corrected = path.with_suffix(expected_suffix)
        warn(
            f"Warning: '{key}' value '{original}' does not end with "
            f"'{expected_suffix}'. Automatically changed to '{corrected}'.",
            verbose=verbose,
        )
        return corrected
    return path


def load_env_config() -> dict:
    """
    Load and validate all pipeline configuration from environment variables.
    - Mandatory variables raise EnvironmentError if absent.
    - Returns a same dict shape with env var values.
    """
    api_url = require("API_URL")

    verbose = as_int(read_optional("VERBOSE", "1"), key="WB_VERBOSE")

    language_raw = os.getenv("LANGUAGE", "").strip()
    if not language_raw:
        language = "en"
        inform("Missing 'LANGUAGE'. Defaulting to 'en'.", verbose=verbose)
    else:
        language = language_raw

    tls_raw = os.getenv("TLS_VERIFY", "").strip()
    if not tls_raw:
        tls_verify = True
        inform("Missing 'TLS_VERIFY'. Defaulting to True.", verbose=verbose)
    else:
        tls_verify = parse_bool(tls_raw, key="TLS_VERIFY", default=True)

    search_wikibase_raw = os.getenv("SEARCH_WIKIBASE", "").strip()
    if not search_wikibase_raw:
        search_wikibase = True
        inform("Missing 'SEARCH_WIKIBASE'. Defaulting to True.", verbose=verbose)
    else:
        search_wikibase = parse_bool(
            search_wikibase_raw, key="SEARCH_WIKIBASE", default=True
        )

    store_raw = os.getenv("STORE_FILE", "").strip()
    if not store_raw:
        store_file = False
    else:
        store_file = parse_bool(store_raw, key="STORE_FILE", default=False)

    lookup_raw = os.getenv("LOOKUP_FILE", "").strip()
    if not lookup_raw:
        if store_file:
            lookup_raw = "data/lookup/lookup.json"
            inform(
                "Missing 'LOOKUP_FILE'. Defaulting to 'data/lookup/lookup.json'.",
                verbose=verbose,
            )
        lookup_file = resolve_path(lookup_raw) if lookup_raw else None
    else:
        lookup_file = resolve_path(lookup_raw)

    if lookup_file is not None:
        lookup_file = ensure_suffix(
            lookup_file,
            ".json",
            key="LOOKUP_FILE",
            verbose=verbose,
        )

    rml_mapping_raw = os.getenv("RML_MAPPING_PATH", "").strip()
    if not rml_mapping_raw:
        rml_mapping_raw = "data/mappings/converted_mapping.ttl"
        inform(
            "Missing 'RML_MAPPING_PATH'. Defaulting to "
            "'data/mappings/converted_mapping.ttl'.",
            verbose=verbose,
        )

    schema_output_raw = os.getenv("SCHEMA_OUTPUT_PATH", "").strip()
    if not schema_output_raw:
        schema_output_raw = "data/output/schema.ttl"
        inform(
            "Missing 'SCHEMA_OUTPUT_PATH'. Defaulting to 'data/output/schema.ttl'.",
            verbose=verbose,
        )

    rml_output_raw = os.getenv("RML_OUTPUT_PATH", "").strip()
    if not rml_output_raw:
        rml_output_raw = "data/output/output.nt"
        inform(
            "Missing 'RML_OUTPUT_PATH'. Defaulting to 'data/output/output.nt'.",
            verbose=verbose,
        )

    rml_mapping_path = resolve_path(rml_mapping_raw)
    schema_output_path = resolve_path(schema_output_raw)
    rml_output_path = resolve_path(rml_output_raw)

    rml_mapping_path = ensure_suffix(
        rml_mapping_path,
        ".ttl",
        key="RML_MAPPING_PATH",
        verbose=verbose,
    )
    schema_output_path = ensure_suffix(
        schema_output_path,
        ".ttl",
        key="SCHEMA_OUTPUT_PATH",
        verbose=verbose,
    )
    rml_output_path = ensure_suffix(
        rml_output_path,
        ".nt",
        key="RML_OUTPUT_PATH",
        verbose=verbose,
    )

    return {
        "wikibase": {
            "api_url": api_url,
            "language": language,
            "tls_verify": tls_verify,
            "search_wikibase": search_wikibase,
            "verbose": verbose,
        },
        "cache": {
            "lookup_file": str(lookup_file),
            "store_file": store_file,
        },
        "paths": {
            "rml_mapping": str(rml_mapping_path),
            "schema_output": str(schema_output_path),
            "rml_output": str(rml_output_path),
        },
    }
