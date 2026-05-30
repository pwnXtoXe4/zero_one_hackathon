"""
CarbonEdge -- centralised logging configuration.

All modules call `logging.getLogger(__name__)` and emit through that. The
runtime (CLI, notebook, tests) calls `configure_logging()` once to install
handlers and pick a level.

Levels we actually use:
  DEBUG    -- per-tick values, intermediate computations, branch decisions
  INFO     -- pipeline phase transitions, file loads, decision outcomes
  WARNING  -- recoverable data issues, fallbacks, missing inputs
  ERROR    -- unrecoverable failures (we usually still raise on top)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Optional

DEFAULT_FORMAT = "%(asctime)s %(levelname)-5s %(name)s | %(message)s"
DEFAULT_DATEFMT = "%H:%M:%S"

_CONFIGURED: bool = False


def configure_logging(
    level: Optional[str | int] = None,
    *,
    stream=None,
    fmt: str = DEFAULT_FORMAT,
    datefmt: str = DEFAULT_DATEFMT,
    force: bool = False,
) -> logging.Logger:
    """Install a single stderr handler on the ``carbonedge`` logger.

    Parameters
    ----------
    level
        Either a string ("DEBUG"/"INFO"/...) or a logging constant. When
        ``None``, falls back to the ``CARBONEDGE_LOG_LEVEL`` env var, then to
        ``INFO``.
    stream
        Output stream (default: ``sys.stderr``).
    fmt, datefmt
        Override the default format strings.
    force
        Re-install the handler even if logging has already been configured.

    Returns the ``carbonedge`` root logger so callers can attach extra
    handlers (e.g. a file handler) when they want to.
    """
    global _CONFIGURED

    root = logging.getLogger("carbonedge")

    if _CONFIGURED and not force:
        if level is not None:
            root.setLevel(_coerce_level(level))
        return root

    # Resolve level: explicit arg > env var > INFO
    if level is None:
        level = os.environ.get("CARBONEDGE_LOG_LEVEL", "INFO")
    resolved = _coerce_level(level)

    # Wipe any previous handlers we installed before re-attaching.
    for h in list(root.handlers):
        root.removeHandler(h)

    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(fmt=fmt, datefmt=datefmt))
    handler.setLevel(resolved)

    root.addHandler(handler)
    root.setLevel(resolved)
    # Don't double-emit through the bare-root logger if the host also configured it.
    root.propagate = False

    _CONFIGURED = True
    return root


def _coerce_level(level: str | int) -> int:
    if isinstance(level, int):
        return level
    name = str(level).strip().upper()
    if name.isdigit():
        return int(name)
    value = logging.getLevelName(name)
    if isinstance(value, int):
        return value
    raise ValueError(f"Unknown log level: {level!r}")
