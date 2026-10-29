"""Exceptions for pysmlight"""


class SmlightError(Exception):
    """Generic SMLIGHT exception."""


class SmlightConnectionError(SmlightError):
    """SMLIGHT connection exception."""


class SmlightCatalogError(SmlightError, ValueError):
    """SMLIGHT firmware catalog validation or lookup exception."""


class SmlightAuthError(SmlightError):
    """SMLIGHT authentication exception."""
