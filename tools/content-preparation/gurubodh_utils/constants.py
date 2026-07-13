CONVERSION_JOB_SCHEMA_VERSION = "1.3.0"
PREVIOUS_CONVERSION_JOB_SCHEMA_VERSION = "1.2.0"
CHAPTER_METADATA_SCHEMA_VERSION = "1.2.0"

PIPELINE_LEGACY_DOCX_TO_UNICODE = "legacy-docx-to-unicode"
PIPELINE_UNICODE_DOCX_INGEST = "unicode-docx-ingest"

ENTRY_POINT_RUN = "python3 -m gurubodh_utils run"
ENTRY_POINT_LEGACY_DOCX_TO_UNICODE = "python3 -m gurubodh_utils legacy-convert"
ENTRY_POINT_UNICODE_DOCX_INGEST = "python3 -m gurubodh_utils unicode-ingest"

PIPELINE_ENTRY_POINTS = {
    PIPELINE_LEGACY_DOCX_TO_UNICODE: ENTRY_POINT_LEGACY_DOCX_TO_UNICODE,
    PIPELINE_UNICODE_DOCX_INGEST: ENTRY_POINT_UNICODE_DOCX_INGEST,
}

SUPPORTED_LEGACY_ENCODINGS = {"aps", "shreelipi"}
SUPPORTED_FONT_ENCODINGS = SUPPORTED_LEGACY_ENCODINGS | {"unicode"}

FORMATTING_PROVIDER_SARVAM = "sarvam"
SUPPORTED_FORMATTING_PROVIDERS = {FORMATTING_PROVIDER_SARVAM}
SUPPORTED_FORMATTING_MODELS = {"sarvam-30b", "sarvam-105b"}
SUPPORTED_FORMATTING_OUTPUT_FORMATS = {"json", "markdown"}
SUPPORTED_FORMATTING_REGENERATE_MODES = {"when-source-checksum-changes"}

DEFAULT_FORMATTING_CONFIG = {
    "enabled": False,
    "provider": FORMATTING_PROVIDER_SARVAM,
    "model": "sarvam-30b",
    "fallback_model": "sarvam-105b",
    "output_formats": ["json", "markdown"],
    "continue_on_error": True,
    "delay_seconds": 5,
    "max_retries": 3,
    "regenerate": "when-source-checksum-changes",
}
