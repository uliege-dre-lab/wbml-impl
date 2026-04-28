import configparser
from pathlib import Path
from unittest.mock import Mock

import pytest

from wikibase_pipeline.rml_executor import (
    _build_morph_kgc_ini,
    check_nt_line_prefixes,
    rml_execute,
)


def test_build_morph_kgc_ini_contains_paths():
    mapping_path = Path("mapping.ttl")
    output_path = Path("output.nt")

    ini_content = _build_morph_kgc_ini(mapping_path, output_path)

    config = configparser.ConfigParser()
    config.read_string(ini_content)

    assert config["CONFIGURATION"]["output_file"] == str(output_path)
    assert config["CONFIGURATION"]["number_of_processes"] == "1"
    assert config["DataSource1"]["mappings"] == str(mapping_path)


def test_rml_execute_raises_if_mapping_file_missing(tmp_path):
    missing_mapping = tmp_path / "missing.ttl"
    output_file = tmp_path / "output.nt"

    with pytest.raises(FileNotFoundError, match="RML mapping file not found"):
        rml_execute(missing_mapping, output_file, verbose=0)


def test_rml_execute_raises_if_morph_kgc_fails(tmp_path, monkeypatch):
    mapping_file = tmp_path / "mapping.ttl"
    output_file = tmp_path / "output.nt"

    mapping_file.write_text("@prefix ex: <https://example.org/> .", encoding="utf-8")

    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error message"
    mock_result.stdout = "output message"

    monkeypatch.setattr(
        "wikibase_pipeline.rml_executor.subprocess.run",
        lambda *args, **kwargs: mock_result,
    )

    with pytest.raises(RuntimeError, match="Morph-KGC execution failed"):
        rml_execute(mapping_file, output_file, verbose=0)


def test_rml_execute_returns_output_path_on_success(tmp_path, monkeypatch):
    mapping_file = tmp_path / "mapping.ttl"
    output_file = tmp_path / "output.nt"

    mapping_file.write_text("@prefix ex: <https://example.org/> .", encoding="utf-8")

    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stderr = ""
    mock_result.stdout = ""

    def fake_run(*args, **kwargs):
        output_file.write_text(
            "<https://example.org/s> <https://example.org/p>"
            " <https://example.org/o> .\n",
            encoding="utf-8",
        )
        return mock_result

    monkeypatch.setattr(
        "wikibase_pipeline.rml_executor.subprocess.run",
        fake_run,
    )

    result = rml_execute(mapping_file, output_file, verbose=0)

    assert result == output_file.resolve()
    assert output_file.exists()


def test_validate_nt_file_accepts_valid_nt(tmp_path):
    nt_file = tmp_path / "valid.nt"

    nt_file.write_text(
        "<https://example.org/s> <https://example.org/p> <https://example.org/o> .\n"
        '_:b0 <https://example.org/p> "literal" .\n',
        encoding="utf-8",
    )

    check_nt_line_prefixes(nt_file)


def test_validate_nt_file_rejects_malformed_line(tmp_path):
    nt_file = tmp_path / "invalid.nt"

    nt_file.write_text(
        "this is not valid n-triples\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Malformed N-Triples line 1"):
        check_nt_line_prefixes(nt_file)
