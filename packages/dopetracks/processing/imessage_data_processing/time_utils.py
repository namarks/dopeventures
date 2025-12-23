"""Time utilities for Messages database processing."""
from datetime import datetime

# Apple timestamp epoch (January 1, 2001)
APPLE_EPOCH = datetime(2001, 1, 1)


def convert_to_apple_timestamp(date_str: str) -> int:
    """Convert ISO date string to Apple timestamp (nanoseconds since 2001-01-01)."""
    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        # Assume local time if no timezone
        dt = dt.replace(tzinfo=None)
    delta = dt - APPLE_EPOCH
    return int(delta.total_seconds() * 1e9)
