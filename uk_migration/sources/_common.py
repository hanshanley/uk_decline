"""Shared fetch helper for the Home Office detailed-dataset sources.

The visa, asylum, and irregular-arrival sources each resolve a dated xlsx attachment from
the same gov.uk page, download it, and hand a named sheet's rows to a parser. This helper
captures that common flow so each source module only declares its prefix, sheet, and parse.
"""

from __future__ import annotations

from typing import Callable, Iterable

from .._govuk import govuk_attachment
from .._http import get_bytes
from .._spreadsheet import read_rows


def fetch_home_office(prefix: str, sheet: str, parse: Callable[[Iterable[tuple]], list[dict]]) -> list[dict]:
    """Resolve the newest attachment for ``prefix``, download it, and ``parse`` ``sheet``."""
    url, filename = govuk_attachment(prefix)
    content = get_bytes(url)
    return parse(read_rows(content, filename, sheet=sheet))
