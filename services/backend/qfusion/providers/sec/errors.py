"""Typed failures raised at the SEC EDGAR provider boundary."""


class SecPayloadError(ValueError):
    """The SEC payload did not satisfy the documented adapter contract."""


class SecTransportError(RuntimeError):
    """The fixed-origin SEC HTTP request failed within bounded retries."""


class SecNetworkPolicyError(PermissionError):
    """The SEC origin did not resolve exclusively to public addresses."""
