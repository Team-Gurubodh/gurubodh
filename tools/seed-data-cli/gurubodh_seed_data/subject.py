from gurubodh_seed_data.config import load_seed_data_config


SUBJECT_WORKFLOW = "subject"


def list_subject_sources():
    return load_seed_data_config().sources_for_workflow(SUBJECT_WORKFLOW)


def subject_source_keys():
    return tuple(source.key for source in list_subject_sources())


def get_subject_source(source_key):
    return load_seed_data_config().get_source(SUBJECT_WORKFLOW, source_key)
