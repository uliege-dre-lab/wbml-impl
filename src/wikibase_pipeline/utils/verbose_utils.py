def warn(msg: str, verbose: int) -> None:
    if verbose >= 1:
        print(f"Warning: {msg}")


def inform(msg: str, verbose: int) -> None:
    if verbose >= 2:
        print(f"Info: {msg}")
