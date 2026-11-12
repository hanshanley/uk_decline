"""Shared HTTP + OECD-SDMX helpers: a pooled session with polite retry/backoff.

The OECD SDMX REST API (https://sdmx.oecd.org/public/rest/data) is free and needs no
API key. We request the ``csvfilewithlabels`` representation and parse it with the
stdlib ``csv`` module, which keeps the dependency surface identical to the sibling
``europe_data`` / ``tuition`` packages.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import requests
from europe_data._http import get_text as _get_text

USER_AGENT = "uk_decline-tax/0.1 (UK vs EU vs US tax-burden comparison; local use)"

_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        s = requests.Session()
        s.headers.update({"User-Agent": USER_AGENT})
        _session = s
    return _session


def get_text(url: str, params: dict[str, Any] | None = None, timeout: int = 90) -> str:
    """GET ``url`` and return the response body as text, retrying transient errors."""
    return _get_text(url, params=params, timeout=timeout, client=session())


def sdmx_csv(
    dataflow: str,
    key: str,
    start: int,
    end: int,
    base: str,
) -> list[dict[str, str]]:
    """Fetch an OECD SDMX data slice as parsed ``csvfilewithlabels`` rows.

    ``dataflow`` is e.g. ``OECD.CTP.TPS,DSD_REV_COMP_OECD@DF_RSOECD,2.0``, ``key`` is
    the dot-delimited dimension key (empty positions act as wildcards), and ``base`` is
    the SDMX endpoint (canonical value lives in :data:`tax.config.SDMX_BASE`). Returns a
    list of dict rows keyed by CSV column name.
    """
    url = f"{base}/{dataflow}/{key}"
    text = get_text(
        url,
        params={
            "startPeriod": str(start),
            "endPeriod": str(end),
            "format": "csvfilewithlabels",
        },
    )
    return list(csv.DictReader(io.StringIO(text)))
