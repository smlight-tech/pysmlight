"""Exceptions for pysmlight"""


class SmlightError(Exception):
    """Generic SMLIGHT exception."""


class SmlightConnectionError(SmlightError):
    """SMLIGHT connection exception."""


class SmlightAuthError(SmlightError):
    """SMLIGHT authentication exception."""
