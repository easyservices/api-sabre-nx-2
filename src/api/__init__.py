# Copyright (c) 2025 harokku999@gmail.com
# Licensed under the MIT License - https://opensource.org/licenses/MIT

from src.settings import get_settings


def load_config():
    """Load FastAPI settings from validated environment variables."""
    settings = get_settings()
    return {"fastapi": settings.fastapi_dict}
