# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

"""Core application package for common helpers.

This package contains common helpers for all functions and classes.
"""

import os
from fastapi.security import HTTPBasic
import yaml


security = HTTPBasic()

def load_config():
    """Load configuration from YAML file."""
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    with open(config_path, 'r', encoding='utf-8') as file:
        return yaml.safe_load(file)