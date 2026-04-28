import pytest

from wikibase_pipeline.config import (
    as_int,
    load_env_config,
    parse_bool,
    require,
)


def clear_config_env(monkeypatch):
    keys = [
        "WB_API_URL",
        "WB_LANGUAGE",
        "WB_VERBOSE",
        "WB_TLS_VERIFY",
        "WB_LOOKUP_FILE",
        "WB_STORE_FILE",
        "RML_MAPPING_PATH",
        "SCHEMA_OUTPUT_PATH",
        "RML_OUTPUT_PATH",
    ]
    for key in keys:
        monkeypatch.delenv(key, raising=False)


# ───────────────────────────
# parse_bool
# ───────────────────────────


def test_parse_bool_true_strings():
    assert parse_bool("true", key="X") is True
    assert parse_bool("1", key="X") is True
    assert parse_bool("yes", key="X") is True


def test_parse_bool_false_strings():
    assert parse_bool("false", key="X") is False
    assert parse_bool("0", key="X") is False
    assert parse_bool("no", key="X") is False


def test_parse_bool_default():
    assert parse_bool(None, key="X", default=True) is True
    assert parse_bool("", key="X", default=False) is False


def test_parse_bool_invalid():
    with pytest.raises(ValueError):
        parse_bool("maybe", key="X")


# ───────────────────────────
# require
# ───────────────────────────


def test_require_ok(monkeypatch):
    monkeypatch.setenv("API_URL", "http://test")
    assert require("API_URL") == "http://test"


def test_require_missing(monkeypatch):
    monkeypatch.delenv("API_URL", raising=False)

    with pytest.raises(EnvironmentError):
        require("API_URL")


# ───────────────────────────
# as_int
# ───────────────────────────


def testas_int_valid():
    assert as_int("5", key="X") == 5


def testas_int_invalid():
    with pytest.raises(ValueError):
        as_int("abc", key="X")


# ───────────────────────────
# load_env_config (core)
# ───────────────────────────


def test_load_env_config_minimal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("API_URL", "http://test")

    mapping = tmp_path / "data/mappings/converted_mapping.ttl"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text("dummy")

    result = load_env_config()

    assert result["wikibase"]["api_url"] == "http://test"
    assert result["wikibase"]["language"] == "en"
    assert result["wikibase"]["tls_verify"] is True
    assert result["wikibase"]["verbose"] == 1

    assert result["paths"]["rml_mapping"].endswith(".ttl")
    assert result["paths"]["schema_output"].endswith(".ttl")
    assert result["paths"]["rml_output"].endswith(".nt")


# ───────────────────────────
# suffix auto-correction
# ───────────────────────────


def test_suffix_auto_correction(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("API_URL", "http://test")

    # wrong suffix on purpose
    monkeypatch.setenv("RML_OUTPUT_PATH", "out.ttl")
    monkeypatch.setenv("SCHEMA_OUTPUT_PATH", "schema.nt")
    monkeypatch.setenv("RML_MAPPING_PATH", "mapping.nt")

    # create corrected mapping file (.ttl expected)
    mapping = tmp_path / "mapping.ttl"
    mapping.write_text("dummy")

    result = load_env_config()

    assert result["paths"]["rml_output"].endswith(".nt")
    assert result["paths"]["schema_output"].endswith(".ttl")
    assert result["paths"]["rml_mapping"].endswith(".ttl")


# ───────────────────────────
# boolean parsing in config
# ───────────────────────────


def test_boolean_env_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    monkeypatch.setenv("API_URL", "http://test")
    monkeypatch.setenv("TLS_VERIFY", "false")
    monkeypatch.setenv("STORE_FILE", "true")

    mapping = tmp_path / "data/mappings/converted_mapping.ttl"
    mapping.parent.mkdir(parents=True, exist_ok=True)
    mapping.write_text("dummy")

    result = load_env_config()

    assert result["wikibase"]["tls_verify"] is False
    assert result["cache"]["store_file"] is True
