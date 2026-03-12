from pathlib import Path

import pytest

from wikibase_pipeline.config import (
    as_int,
    load_config_ini,
    load_pipeline_ini,
    parse_bool,
)


def test_parse_bool_true_strings():
    assert parse_bool("true", default=False, verbose=0) is True
    assert parse_bool("1", default=False, verbose=0) is True
    assert parse_bool("yes", default=False, verbose=0) is True
    assert parse_bool("on", default=False, verbose=0) is True


def test_parse_bool_false_strings():
    assert parse_bool("false", default=True, verbose=0) is False
    assert parse_bool("0", default=True, verbose=0) is False
    assert parse_bool("no", default=True, verbose=0) is False
    assert parse_bool("off", default=True, verbose=0) is False


def test_parse_bool_none_returns_default():
    assert parse_bool(None, default=True, verbose=0) is True
    assert parse_bool(None, default=False, verbose=0) is False


def test_parse_bool_bool_input():
    assert parse_bool(True, default=False, verbose=0) is True
    assert parse_bool(False, default=True, verbose=0) is False


def test_parse_bool_unknown_returns_default():
    assert parse_bool("maybe", default=True, verbose=0) is True
    assert parse_bool("maybe", default=False, verbose=0) is False


def test_as_int_valid():
    assert as_int("12", key="verbose", section="wikibase") == 12
    assert as_int(" 7 ", key="verbose", section="wikibase") == 7


def test_as_int_invalid():
    with pytest.raises(ValueError, match=r"Invalid int for \[wikibase\] verbose"):
        as_int("abc", key="verbose", section="wikibase")


def test_load_config_ini_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config_ini(Path("does_not_exist.ini"))


def test_load_config_ini_no_sections(tmp_path):
    cfg = tmp_path / "config.ini"
    cfg.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="No sections found"):
        load_config_ini(cfg)


def test_load_config_ini_missing_output_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mapping = tmp_path / "mapping.ttl"
    mapping.write_text("dummy", encoding="utf-8")

    cfg = tmp_path / "config.ini"
    cfg.write_text(
        f"[DataSource1]\nmappings = {mapping.name}\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No 'output_file' defined"):
        load_config_ini(cfg)


def test_load_config_ini_missing_mappings(tmp_path):
    cfg = tmp_path / "config.ini"
    cfg.write_text(
        "[CONFIGURATION]\noutput_file = out.nt\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="No 'mappings' defined"):
        load_config_ini(cfg)


def test_load_config_ini_mapping_file_not_found(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = tmp_path / "config.ini"
    cfg.write_text(
        "[CONFIGURATION]\n"
        "output_file = out.nt\n\n"
        "[DataSource1]\n"
        "mappings = missing.ttl\n",
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match="Mapping file not found"):
        load_config_ini(cfg)


def test_load_config_ini_changes_output_suffix_to_nt(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mapping = tmp_path / "mapping.ttl"
    mapping.write_text("dummy", encoding="utf-8")

    cfg = tmp_path / "config.ini"
    cfg.write_text(
        "[CONFIGURATION]\n"
        "output_file = out.ttl\n\n"
        "[DataSource1]\n"
        f"mappings = {mapping.name}\n",
        encoding="utf-8",
    )

    data, output_value = load_config_ini(cfg, verbose=0)

    assert output_value == "out.nt"
    assert data["CONFIGURATION"]["output_file"] == "out.nt"


def test_load_config_ini_resolves_relative_mapping_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    mapping = tmp_path / "mapping.ttl"
    mapping.write_text("dummy", encoding="utf-8")

    cfg = tmp_path / "config.ini"
    cfg.write_text(
        "[CONFIGURATION]\n"
        "output_file = out.nt\n\n"
        "[DataSource1]\n"
        "mappings = mapping.ttl\n",
        encoding="utf-8",
    )

    data, output_value = load_config_ini(cfg)

    assert data["DataSource1"]["mappings"] == "mapping.ttl"
    assert output_value == "out.nt"


def test_load_pipeline_ini_missing_file():
    with pytest.raises(FileNotFoundError):
        load_pipeline_ini("missing_pipeline.ini")


def test_load_pipeline_ini_no_sections(tmp_path):
    cfg = tmp_path / "pipeline.ini"
    cfg.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="No sections found in pipeline ini"):
        load_pipeline_ini(cfg)


def test_load_pipeline_ini_missing_api_url(tmp_path):
    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\nlanguage = en\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match=r"Missing required field: \[wikibase\] api_url"
    ):
        load_pipeline_ini(cfg)


def test_load_pipeline_ini_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\napi_url = https://example.org/w/api.php\n",
        encoding="utf-8",
    )

    result = load_pipeline_ini(cfg)

    assert result["wikibase"]["api_url"] == "https://example.org/w/api.php"
    assert result["wikibase"]["language"] == "en"
    assert result["wikibase"]["tls_verify"] is True
    assert result["wikibase"]["create_missing_properties"] is False
    assert result["wikibase"]["verbose"] == 1
    assert result["wikibase"]["sparql_endpoint"] is None

    assert result["urn"]["item_prefix"] == "urn:wikibase:Q:"
    assert result["urn"]["property_prefix"] == "urn:wikibase:P:"

    assert result["cache"]["store_file"] is False
    assert result["cache"]["lookup_file"] == str(
        (tmp_path / "data/lookup/lookup.json").resolve()
    )


def test_load_pipeline_ini_invalid_verbose(tmp_path):
    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\napi_url = https://example.org/w/api.php\nverbose = abc\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=r"Invalid int for \[wikibase\] verbose"):
        load_pipeline_ini(cfg)


def test_load_pipeline_ini_same_item_and_property_prefix(tmp_path):
    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\n"
        "api_url = https://example.org/w/api.php\n\n"
        "[urn]\n"
        "item_prefix = urn:test:\n"
        "property_prefix = urn:test:\n",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError, match="item_prefix and property_prefix cannot be the same"
    ):
        load_pipeline_ini(cfg)


def test_load_pipeline_ini_boolean_values(tmp_path):
    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\n"
        "api_url = https://example.org/w/api.php\n"
        "tls_verify = false\n"
        "create_missing_properties = yes\n\n"
        "[cache]\n"
        "store_file = true\n",
        encoding="utf-8",
    )

    result = load_pipeline_ini(cfg)

    assert result["wikibase"]["tls_verify"] is False
    assert result["wikibase"]["create_missing_properties"] is True
    assert result["cache"]["store_file"] is True


def test_load_pipeline_ini_resolves_relative_lookup_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    cfg = tmp_path / "pipeline.ini"
    cfg.write_text(
        "[wikibase]\n"
        "api_url = https://example.org/w/api.php\n\n"
        "[cache]\n"
        "lookup_file = cache/my_lookup.json\n",
        encoding="utf-8",
    )

    result = load_pipeline_ini(cfg)

    assert result["cache"]["lookup_file"] == str(
        (tmp_path / "cache/my_lookup.json").resolve()
    )
