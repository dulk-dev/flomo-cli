"""Stable error-code mapping for structured CLI output.

Maps domain exceptions to fixed strings so Agents can reliably
branch on error type without parsing human-readable messages.
"""

from .exceptions import (
    FlomoApiError,
    NotAuthenticatedError,
    NotFoundError,
    ValidationError,
)


def error_code_for_exception(exc: Exception) -> str:
    """Return a stable error-code string for the given exception."""
    if isinstance(exc, NotAuthenticatedError):
        return "not_authenticated"
    if isinstance(exc, NotFoundError):
        return "not_found"
    if isinstance(exc, ValidationError):
        return "validation_error"
    if isinstance(exc, FlomoApiError):
        return "api_error"
    return "unknown_error"
