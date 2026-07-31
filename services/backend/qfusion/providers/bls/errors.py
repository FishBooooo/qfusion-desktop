"""Typed failures raised at the BLS Public Data API boundary."""


class BlsPayloadError(ValueError):
    """The BLS payload did not satisfy the documented monthly-series contract."""


class BlsTransportError(RuntimeError):
    """The fixed-origin BLS request failed within bounded retries."""


class BlsNetworkPolicyError(PermissionError):
    """The BLS origin did not resolve exclusively to public addresses."""


class BlsRateLimitError(PermissionError):
    """The project-local unregistered BLS request budget was exhausted."""
