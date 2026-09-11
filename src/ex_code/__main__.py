"""Entrypoint for the ex-code CLI tool."""

import sys

from ex_code.cli.app import run_app


def main() -> None:
    """Main CLI entrypoint."""
    sys.exit(run_app())


if __name__ == "__main__":
    main()
