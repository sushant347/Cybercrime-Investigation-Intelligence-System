"""Typed failures exposed by the standalone RAG engine."""


class RAGError(RuntimeError):
    """Base class for an expected RAG failure."""


class ArtifactContractError(RAGError):
    """A CIIS source artifact is malformed or belongs to another case."""


class IndexUnavailableError(RAGError):
    """The vector index cannot be opened or queried."""


class GenerationUnavailableError(RAGError):
    """The configured local generation service cannot be reached."""


class GenerationTimeoutError(GenerationUnavailableError):
    """The local model did not answer within the configured deadline."""


class GenerationResponseError(RAGError):
    """The generation service returned an invalid response."""
