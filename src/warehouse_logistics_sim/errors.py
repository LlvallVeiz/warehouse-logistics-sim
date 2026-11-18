"""Shared error type for the warehouse logistics simulator."""


class ValidationError(ValueError):
    """Raised when user input (layout, SKU, scenario, CLI args) is invalid."""
