# pylint: disable=locally-disabled, missing-docstring

import configparser


class ConfigError(Exception):
    """Configuration error"""


def get_config_options(**kwargs):
    """Simple function to parse a local config file for required options.

    Args:
        **config (str): Keyword argument to optionally specify the local config file name to
                        open and read options from.

    Returns:
        dict: Returns a dictionary object containing all of the necessary config options.

    """
    config_file = kwargs.get("config", "config.cfg")
    config = configparser.ConfigParser()
    config.read(config_file)
    config_options = {}
    try:
        config_options["api_secret"] = config.get("Scouter", "api_secret")
        config_options["max_test_count"] = int(config.get("Scouter", "max_test_count"))
        config_options["max_process_count"] = int(config.get("Scouter", "max_process_count"))
    except (configparser.NoSectionError, configparser.NoOptionError) as error:
        raise ConfigError(error)
    return config_options
