"""Domain failures raised below the Gurubodh command-line boundary."""


class GurubodhError(Exception):
    """Base class for expected, user-facing Gurubodh failures."""


class ConfigurationError(GurubodhError):
    """A job, project, or runtime setting is invalid."""


class SourceValidationError(GurubodhError):
    """Source material or its provenance cannot be trusted."""


class StorageError(GurubodhError):
    """A local or remote storage operation failed."""


class PublicationError(StorageError):
    """Validated artifacts could not be published safely."""


class ProcessingError(GurubodhError):
    """A content-processing operation could not complete."""
