from gurubodh_seed_data.config import load_seed_data_config


def list_workflows():
    return load_seed_data_config().workflows
