from gurubodh_seed_data.config import load_seed_data_config


CATEGORY_WORKFLOW = "category"


def list_category_sources():
    return load_seed_data_config().sources_for_workflow(CATEGORY_WORKFLOW)


def category_source_keys():
    return tuple(source.key for source in list_category_sources())


def get_category_source(source_key):
    return load_seed_data_config().get_source(CATEGORY_WORKFLOW, source_key)
