"""Smoke tests to verify project setup and basic module import."""

import ex_code
from ex_code.__main__ import main


def test_import_ex_code():
    """Verify ex_code can be imported."""
    assert ex_code is not None


def test_main_entrypoint(capsys):
    """Verify main entrypoint executes without error."""
    main()
    captured = capsys.readouterr()
    assert "ex-code" in captured.out
