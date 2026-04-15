from __future__ import annotations

import sys
from typing import Iterable, TextIO


def write_line(text: str = "", *, file: TextIO = sys.stdout) -> None:
    print(text, file=file)


def write_key_values(
    items: Iterable[tuple[str, object]],
    *,
    file: TextIO = sys.stdout,
) -> None:
    for key, value in items:
        write_line(f"{key}: {value}", file=file)


def write_section(
    title: str,
    lines: Iterable[str],
    *,
    file: TextIO = sys.stdout,
) -> None:
    write_line(title, file=file)
    for line in lines:
        write_line(line, file=file)


def write_error(message: str) -> None:
    write_line(message, file=sys.stderr)
