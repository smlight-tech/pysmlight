"""Exceptions for pysmlight"""


class SmlightError(Exception):
    """Generic SMLIGHT exception."""


class SmlightConnectionError(SmlightError):
    """SMLIGHT connection exception."""


class SmlightCatalogError(SmlightConnectionError, ValueError):
    """SMLIGHT firmware catalog validation or lookup exception."""


class SmlightAuthError(SmlightError):
    """SMLIGHT authentication exception."""
