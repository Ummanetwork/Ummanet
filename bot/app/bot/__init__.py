from __future__ import annotations

from typing import Any, Awaitable, Callable

__all__ = ["main"]


def main(*args: Any, **kwargs: Any) -> Awaitable[Any]:
    # Lazy import to avoid importing runtime-only dependencies (e.g. redis) on package import.
    from .bot import main as _main

    return _main(*args, **kwargs)
