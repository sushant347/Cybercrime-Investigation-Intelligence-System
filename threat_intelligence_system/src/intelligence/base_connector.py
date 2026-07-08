"""
Abstract base for threat intelligence connectors.

Defines the ``IntelligenceResult`` dataclass (the canonical return type for
every connector) and the ``BaseConnector`` ABC that each concrete data-source
adapter must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class IntelligenceResult:
    """Standardised result returned by every intelligence connector.

    Attributes:
        source: Name of the connector that produced this result.
        domain: The domain that was queried.
        data: Arbitrary key/value intelligence payload.
        success: Whether the query completed without error.
        error_message: Human-readable error description when ``success`` is False.
        query_timestamp: ISO 8601 UTC timestamp of query execution.
    """

    source: str
    domain: str
    data: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error_message: str | None = None
    query_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        """Serialise the result to a plain dictionary.

        Returns:
            Dictionary representation suitable for JSON serialisation.
        """
        return asdict(self)


class BaseConnector(ABC):
    """Abstract base class for all threat intelligence connectors.

    Subclasses must implement:
    * ``name`` -- a read-only property returning the connector's identifier.
    * ``query`` -- the method that performs the intelligence lookup.

    Optionally override ``is_available`` to indicate whether the connector's
    prerequisites (API keys, databases, etc.) are satisfied.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique connector identifier (e.g. ``'virustotal'``).

        Returns:
            Connector name string.
        """
        ...

    @abstractmethod
    def query(self, domain: str) -> IntelligenceResult:
        """Execute an intelligence lookup for *domain*.

        Args:
            domain: The domain to investigate (e.g. ``'example.com'``).

        Returns:
            An ``IntelligenceResult`` with the lookup payload.
        """
        ...

    def is_available(self) -> bool:
        """Check whether this connector's external dependencies are satisfied.

        The default implementation returns ``True`` (always available).
        Override in subclasses that require API keys or optional libraries.

        Returns:
            ``True`` if the connector is ready for use, ``False`` otherwise.
        """
        return True

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} available={self.is_available()}>"
