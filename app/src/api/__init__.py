import os
import yaml


def _get_config_path():
    """Return the config path, allowing FASTAPI_CONFIG_FILE override."""
    default_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    return os.getenv("FASTAPI_CONFIG_FILE", default_path)


def _override_fastapi_settings(config):
    """Override YAML values with environment variables if provided."""
    fastapi_cfg = config.setdefault("fastapi", {})
    env_overrides = {
        "host": os.getenv("FASTAPI_HOST"),
        "port": os.getenv("FASTAPI_PORT"),
        "reload": os.getenv("FASTAPI_RELOAD"),
        "log_level": os.getenv("FASTAPI_LOG_LEVEL"),
    }

    for key, value in env_overrides.items():
        if value is None:
            continue
        if key == "port":
            fastapi_cfg[key] = int(value)
        elif key == "reload":
            fastapi_cfg[key] = value.lower() in {"1", "true", "yes", "on"}
        else:
            fastapi_cfg[key] = value

    return config


def load_config():
    """Load configuration from YAML file with optional env overrides."""
    config_path = _get_config_path()
    with open(config_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return _override_fastapi_settings(config)
