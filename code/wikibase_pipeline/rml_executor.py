import configparser
import io
import subprocess
import sys
import tempfile
from pathlib import Path

from .utils.verbose_utils import inform


def _build_morph_kgc_ini(
    mapping_path: Path,
    output_path: Path,
) -> str:
    """
    Generate the morph-kgc config.ini content as a string.
    Inputs:
    - mapping_path: path to the RML mapping file
    - output_path: path where the output RDF file will be written
    Output:
    - the content of the config.ini file as a string
    """
    config = configparser.ConfigParser()
    config["CONFIGURATION"] = {
        "output_file": str(output_path),
        "number_of_processes": 1,
    }
    config["DataSource1"] = {
        "mappings": str(mapping_path),
    }

    buf = io.StringIO()
    config.write(buf)
    return buf.getvalue()


def rml_execute(
    mapping_path: Path | str,
    output_path: Path | str,
    verbose: int = 1,
) -> Path:
    """
    Execute the RML mapping using morph-kgc and write the output to a file.
    Inputs:
    - mapping_path: path to the RML mapping file
    - output_path: path where the output RDF file will be written
    - verbose: verbosity level for logging
    Output:
    - the path to the generated RDF file
    """

    mapping_path = Path(mapping_path).resolve()
    output_path = Path(output_path).resolve()
    project_path = Path.cwd()

    if not mapping_path.is_file():
        raise FileNotFoundError(f"RML mapping file not found: {mapping_path}")

    ini_content = _build_morph_kgc_ini(mapping_path, output_path)

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ini", delete=False, dir=project_path
    ) as config_path:
        config_path.write(ini_content)
        config_path.flush()
        tmp_path = Path(config_path.name)

    try:
        result = subprocess.run(
            [sys.executable, "-m", "morph_kgc", str(tmp_path)],
            capture_output=True,
            text=True,
            cwd=project_path,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        raise RuntimeError(
            "Morph-KGC execution failed.\n\n"
            f"STDERR:\n{result.stderr}\n\n"
            f"STDOUT:\n{result.stdout}"
        )

    inform("Morph-KGC execution completed successfully.", verbose)

    if not output_path.is_file():
        raise FileNotFoundError(f"Expected output file not found: {output_path}")

    return output_path


def check_nt_line_prefixes(nt_path: str | Path) -> None:
    """
    Check that the given file is a well-formed N-Triples file
    through its syntax line by line.
    """
    with Path(nt_path).open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.lstrip()
            if not stripped:
                continue
            if not (stripped.startswith("<") or stripped.startswith("_:")):
                raise ValueError(f"Malformed N-Triples line {line_no}: {line.rstrip()}")
