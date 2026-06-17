"""Parsing of raw testbench trace logs into structured LogEntry objects.

The synthetic log format used in this project mimics a typical infotainment
testbench trace line::

    2026-03-01T09:15:02.412 [INFO] MediaPlayer (TC_MEDIA_004): playback started

i.e. ``<iso8601> [<LEVEL>] <Component> (<TestCase>): <message>``. The test
case group is optional. Lines that do not match are kept as raw INFO entries
so that no data is silently dropped -- important when the downstream agent
reasons about completeness.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ..models import LogEntry, LogLevel

_LINE_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s+"
    r"\[(?P<level>[A-Z]+)\]\s+"
    r"(?P<component>[A-Za-z0-9_]+)\s*"
    r"(?:\((?P<tc>[A-Za-z0-9_]+)\))?\s*:\s*"
    r"(?P<msg>.*)$"
)


def _parse_ts(value: str) -> datetime:
    # Python's fromisoformat handles fractional seconds in 3.11+, but be lenient.
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.fromisoformat(value.split(".")[0])


def parse_line(line_no: int, raw: str) -> LogEntry:
    """Parse a single raw line into a LogEntry, never raising on bad input."""
    stripped = raw.rstrip("\n")
    m = _LINE_RE.match(stripped)
    if not m:
        return LogEntry(
            line_no=line_no,
            timestamp=datetime(1970, 1, 1),
            level=LogLevel.INFO,
            component="UNPARSED",
            message=stripped,
            raw=stripped,
        )
    level_str = m.group("level")
    level = LogLevel.__members__.get(level_str, LogLevel.INFO)
    return LogEntry(
        line_no=line_no,
        timestamp=_parse_ts(m.group("ts")),
        level=level,
        component=m.group("component"),
        message=m.group("msg"),
        test_case=m.group("tc"),
        raw=stripped,
    )


def parse_log_file(path: str | Path) -> list[LogEntry]:
    """Parse an entire log file into LogEntry objects."""
    path = Path(path)
    entries: list[LogEntry] = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            entries.append(parse_line(i, line))
    return entries
