import subprocess

import pytest

from wikibase_pipeline.rml_executor import rml_execute


class DummyCompletedProcess:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_rml_execute_success_with_relative_output(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[CONFIGURATION]\noutput_file = out.nt\n", encoding="utf-8")

    expected_output = tmp_path / "out.nt"

    calls = {}

    def fake_run(cmd, capture_output, text):
        calls["cmd"] = cmd
        calls["capture_output"] = capture_output
        calls["text"] = text

        expected_output.write_text("<s> <p> <o> .\n", encoding="utf-8")
        return DummyCompletedProcess(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = rml_execute(config_path, "out.nt", verbose=2)

    assert result == expected_output.resolve()
    assert calls["cmd"] == [
        pytest.importorskip("sys").executable,
        "-m",
        "morph_kgc",
        str(config_path.resolve()),
    ]
    assert calls["capture_output"] is True
    assert calls["text"] is True


def test_rml_execute_failure(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[CONFIGURATION]\noutput_file = out.nt\n", encoding="utf-8")

    def fake_run(cmd, capture_output, text):
        return DummyCompletedProcess(
            returncode=1,
            stdout="some stdout",
            stderr="some stderr",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeError) as excinfo:
        rml_execute(config_path, "out.nt", verbose=1)

    message = str(excinfo.value)
    assert "Morph-KGC execution failed" in message
    assert "some stdout" in message
    assert "some stderr" in message


def test_rml_execute_missing_output_file(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[CONFIGURATION]\noutput_file = out.nt\n", encoding="utf-8")

    def fake_run(cmd, capture_output, text):
        return DummyCompletedProcess(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(FileNotFoundError) as excinfo:
        rml_execute(config_path, "out.nt", verbose=1)

    assert "Expected output file not found" in str(excinfo.value)


def test_rml_execute_success_with_absolute_output(monkeypatch, tmp_path):
    config_path = tmp_path / "config.ini"
    config_path.write_text("[CONFIGURATION]\noutput_file = out.nt\n", encoding="utf-8")

    absolute_output = tmp_path / "nested" / "result.nt"
    absolute_output.parent.mkdir(parents=True, exist_ok=True)

    def fake_run(cmd, capture_output, text):
        absolute_output.write_text("<s> <p> <o> .\n", encoding="utf-8")
        return DummyCompletedProcess(returncode=0, stdout="ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = rml_execute(config_path, str(absolute_output), verbose=1)

    assert result == absolute_output.resolve()
