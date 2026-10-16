"""Time helpers: all timestamps are timezone-aware UTC; display in IST."""
from datetime import timezone, timedelta

from ..db import now  # noqa: F401

IST = timezone(timedelta(hours=5, minutes=30), "IST")
