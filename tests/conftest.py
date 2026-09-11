"""Pytest fixtures and configuration for ex-code test suite."""

import pytest


@pytest.fixture(autouse=True)
def enable_test_offline_mode(monkeypatch):
    """Ensure all automated tests run completely offline, deterministic, and lightweight."""
    monkeypatch.setenv("EX_CODE_OFFLINE", "1")
