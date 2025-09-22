"""Pytest configuration for handling integration tests that require a live Nextcloud instance."""

import os
from typing import Iterable

import pytest


INTEGRATION_TEST_MODULES: Iterable[str] = {
    "test_contacts_api_cli.py",
    "test_contacts_nx_cli.py",
    "test_events_api_cli.py",
    "test_events_nx_cli.py",
}


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip integration tests unless explicitly enabled.

    The repository includes manual integration checks that assume a running
    Nextcloud instance and a populated FastAPI proxy. Those cannot run in the
    automated test environment, so we skip them by default unless the user
    opts in by setting ``RUN_NEXTCLOUD_INTEGRATION_TESTS=1``.
    """

    if os.environ.get("RUN_NEXTCLOUD_INTEGRATION_TESTS") == "1":
        return

    skip_marker = pytest.mark.skip(
        reason=(
            "Nextcloud integration tests require a live server. Set "
            "RUN_NEXTCLOUD_INTEGRATION_TESTS=1 to execute them."
        )
    )

    for item in items:
        if item.fspath.basename in INTEGRATION_TEST_MODULES:
            item.add_marker(skip_marker)
