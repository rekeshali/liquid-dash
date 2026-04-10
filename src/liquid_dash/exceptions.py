class LiquidDashError(Exception):
    """Base exception for liquid_dash."""


class InvalidEventError(LiquidDashError):
    """Raised when an event payload is malformed."""


class UnsafeLayoutError(LiquidDashError):
    """Raised when the validator finds an unsafe layout."""
