"""Shared ML infrastructure errors, independent of consuming workflows."""


class ModelCacheConfigError(RuntimeError):
    """Raised when ML infrastructure cannot resolve the local model cache."""
