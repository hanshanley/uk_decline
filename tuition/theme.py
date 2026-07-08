"""Backwards-compatible shim: the tuition analysis's plotting theme now lives in the
shared :mod:`vizstyle` house style. This module re-exports it so existing
``from tuition import theme`` / ``theme.apply()`` call sites keep working.
"""

from __future__ import annotations

from vizstyle import (  # noqa: F401  (re-exported for back-compat)
    BG, CARD, TEXT, MUTED, GRID, ACCENT, BLUE, GOLD, GREEN,
    RC_PARAMS, PALETTE, source_note, end_label, save_fig, white_stroke,
    house_style as apply,
)

__all__ = [
    "BG", "CARD", "TEXT", "MUTED", "GRID", "ACCENT", "BLUE", "GOLD", "GREEN",
    "RC_PARAMS", "PALETTE", "apply", "source_note", "end_label", "save_fig", "white_stroke",
]
