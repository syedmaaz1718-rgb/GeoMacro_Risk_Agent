"""Extractor 6: India VIX confirmation (spec 5.4)."""
from ..config import cfg
from ._common import _market


def vix(s, now):
    return _market(s, now, "vix_move", "vix_confirmation", cfg()["rules"]["vix"]["thresholds"], "India VIX")
