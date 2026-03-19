"""Semantic exception hierarchy for Flomo CLI."""


class FlomoError(Exception):
    """Base exception for all Flomo CLI errors."""


class FlomoApiError(FlomoError):
    """API returned a non-success response code."""

    def __init__(self, message: str, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class NotAuthenticatedError(FlomoApiError):
    """Token is missing, invalid, or expired (API code -10)."""


class NotFoundError(FlomoApiError):
    """The requested resource was not found."""


class ValidationError(FlomoApiError):
    """Request parameters failed validation."""
