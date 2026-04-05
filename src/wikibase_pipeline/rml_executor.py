import subprocess
import sys
from pathlib import Path

from .utils import inform


def rml_execute(config_path: Path | str, output_value: str, verbose: int) -> Path:
    config_path = Path(config_path).resolve()
    project_path = Path.cwd()

    cmd = [sys.executable, "-m", "morph_kgc", str(config_path)]

    inform(f"Running Morph-KGC with config: {config_path}", verbose)
    inform(f"Expected output file: {output_value}", verbose)

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_path)

    if result.returncode != 0:
        raise RuntimeError(
            "Morph-KGC execution failed.\n\n"
            f"STDERR:\n{result.stderr}\n\n"
            f"STDOUT:\n{result.stdout}"
        )

    inform("Morph-KGC execution completed successfully.", verbose)

    output_path = Path(output_value)

    if not output_path.is_absolute():
        output_path = (project_path / output_path).resolve()
    else:
        output_path = output_path.resolve()

    if not output_path.is_file():
        raise FileNotFoundError(f"Expected output file not found: {output_path}")

    return output_path


def validate_nt_file(nt_path: Path) -> None:
    with nt_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            stripped = line.lstrip()
            if not stripped:
                continue
            if not (stripped.startswith("<") or stripped.startswith("_:")):
                raise ValueError(f"Malformed N-Triples line {line_no}: {line.rstrip()}")
