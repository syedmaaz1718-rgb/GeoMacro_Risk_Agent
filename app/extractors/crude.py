"""Extractor 5: crude confirmation (spec 5.4)."""
from ..config import cfg
from ._common import _market


def crude(s, now):
    return _market(s, now, "crude_move", "crude_confirmation", cfg()["rules"]["crude"]["thresholds"], "Brent crude")
