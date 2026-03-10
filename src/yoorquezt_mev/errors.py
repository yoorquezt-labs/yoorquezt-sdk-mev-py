"""Error types and error codes for Q MEV AI SDK."""

from __future__ import annotations

from typing import Any


MEV_ERROR_CODES: dict[str, str] = {
    "BUNDLE_REVERTED": "Bundle simulation reverted",
    "BUNDLE_UNDERPAID": "Bundle bid too low",
    "BUNDLE_EXPIRED": "Bundle target block has passed",
    "BUNDLE_CONFLICT": "Bundle conflicts with existing bundle",
    "BUNDLE_TOO_LARGE": "Bundle exceeds maximum transaction count",
    "RELAY_TIMEOUT": "Relay response timeout",
    "RELAY_UNAVAILABLE": "Relay is not reachable",
    "RELAY_REJECTED": "Relay rejected the bundle",
    "AUCTION_CLOSED": "Auction for target block is closed",
    "AUCTION_OUTBID": "Bid was outbid by a higher offer",
    "SIMULATION_FAILED": "Bundle simulation encountered an error",
    "SIMULATION_TIMEOUT": "Bundle simulation timed out",
    "AUTH_INVALID": "Invalid API key or credentials",
    "AUTH_EXPIRED": "API key has expired",
    "RATE_LIMITED": "Request rate limit exceeded",
    "INVALID_PARAMS": "Invalid request parameters",
    "INTERNAL_ERROR": "Internal server error",
    "NETWORK_ERROR": "Network connection failed",
    "WS_DISCONNECTED": "WebSocket connection lost",
    "WS_SUBSCRIBE_FAILED": "Failed to subscribe to topic",
}


class QMEVError(Exception):
    """Base error for all Q MEV SDK operations."""

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.details = details

    @classmethod
    def from_code(cls, code: str, details: Any = None) -> QMEVError:
        message = MEV_ERROR_CODES.get(code, f"Unknown error: {code}")
        return cls(code, message, details)

    @classmethod
    def network_error(cls, cause: Any = None) -> QMEVError:
        return cls("NETWORK_ERROR", "Network connection failed", cause)

    @classmethod
    def auth_error(cls) -> QMEVError:
        return cls("AUTH_INVALID", "Invalid API key or credentials")

    @classmethod
    def from_json_rpc_error(cls, error: dict[str, Any]) -> QMEVError:
        code = error.get("code", -1)
        message = error.get("message", "Unknown RPC error")
        data = error.get("data")
        return cls(f"RPC_{code}", message, data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"QMEVError(code={self.code!r}, message={str(self)!r})"
