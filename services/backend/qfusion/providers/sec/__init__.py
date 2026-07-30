"""SEC EDGAR Adapter, contracts, parser, and fixed-origin transport."""

from qfusion.providers.sec.adapter import SecEdgarProvider
from qfusion.providers.sec.capture import (
    SecCaptureManifest,
    build_sec_capture_manifest,
    write_sec_capture_bundle,
)
from qfusion.providers.sec.contracts import (
    SecCik,
    SecFilingRequest,
    SecJsonResponse,
    SecTransportConfig,
    validate_sec_filing_request,
)
from qfusion.providers.sec.errors import (
    SecNetworkPolicyError,
    SecPayloadError,
    SecTransportError,
)
from qfusion.providers.sec.interfaces import SecFilingProvider
from qfusion.providers.sec.parser import parse_sec_submissions
from qfusion.providers.sec.transport import (
    DefaultPublicResolver,
    HostResolver,
    SecHttpTransport,
    SecJsonTransport,
    require_public_addresses,
)

__all__ = [
    "DefaultPublicResolver",
    "HostResolver",
    "SecCaptureManifest",
    "SecCik",
    "SecEdgarProvider",
    "SecFilingProvider",
    "SecFilingRequest",
    "SecHttpTransport",
    "SecJsonResponse",
    "SecJsonTransport",
    "SecNetworkPolicyError",
    "SecPayloadError",
    "SecTransportConfig",
    "SecTransportError",
    "build_sec_capture_manifest",
    "parse_sec_submissions",
    "require_public_addresses",
    "validate_sec_filing_request",
    "write_sec_capture_bundle",
]
