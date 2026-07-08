from gurubodh_seed_data.config import load_seed_data_config


GLOSSARY_WORKFLOW = "glossary"


def list_glossary_sources():
    return load_seed_data_config().sources_for_workflow(GLOSSARY_WORKFLOW)


def glossary_source_keys():
    return tuple(source.key for source in list_glossary_sources())


def get_glossary_source(source_key):
    return load_seed_data_config().get_source(GLOSSARY_WORKFLOW, source_key)
