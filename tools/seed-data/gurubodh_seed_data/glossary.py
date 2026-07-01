from dataclasses import dataclass


@dataclass(frozen=True)
class GlossarySource:
    key: str
    name: str
    csv_filename: str
    json_filename: str


SUPPORTED_GLOSSARY_SOURCES = (
    GlossarySource(
        key="sanatan-glossary",
        name="Sanatan Glossary",
        csv_filename="sanatan-glossary.csv",
        json_filename="sanatan-glossary.json",
    ),
    GlossarySource(
        key="prabodhan-glossary",
        name="Prabodhan Glossary",
        csv_filename="prabodhan-glossary.csv",
        json_filename="prabodhan-glossary.json",
    ),
)


def list_glossary_sources():
    return SUPPORTED_GLOSSARY_SOURCES


def glossary_source_keys():
    return tuple(source.key for source in SUPPORTED_GLOSSARY_SOURCES)


def get_glossary_source(source_key):
    for source in SUPPORTED_GLOSSARY_SOURCES:
        if source.key == source_key:
            return source
    accepted_values = ", ".join(glossary_source_keys())
    raise ValueError(
        f"Unsupported glossary source: {source_key}\n"
        f"Accepted values: {accepted_values}"
    )
