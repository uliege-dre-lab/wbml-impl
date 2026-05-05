def warn(msg: str, verbose: int) -> None:
    """
    Print a warning message if the verbosity level is at least 1.
    Input:
    - msg: The warning message to print.
    - verbose: The verbosity level (integer).
    """
    if verbose >= 1:
        print(f"Warning: {msg}")


def inform(msg: str, verbose: int) -> None:
    """
    Print an information message if the verbosity level is at least 2.
    Input:
    - msg: The information message to print.
    - verbose: The verbosity level (integer).
    """
    if verbose >= 2:
        print(f"Info: {msg}")
