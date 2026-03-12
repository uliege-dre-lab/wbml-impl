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
