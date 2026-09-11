"""Smoke tests to verify project setup and basic module import."""

from unittest.mock import patch

import pytest

import ex_code
from ex_code.__main__ import main


def test_import_ex_code():
    """Verify ex_code can be imported."""
    assert ex_code is not None


def test_main_entrypoint():
    """Verify main entrypoint executes and delegates to run_app without blocking."""
    with (
        patch("ex_code.__main__.run_app", return_value=0),
        pytest.raises(SystemExit) as exc,
    ):
        main()
    assert exc.value.code == 0
