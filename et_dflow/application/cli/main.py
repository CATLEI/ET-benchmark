"""
CLI main entry point.

This module provides the main CLI entry point for the et-dflow command.
"""

# Import cli function from et_dflow.application.cli
# The cli function is now exported from et_dflow.application.cli.__init__
from et_dflow.application.cli import cli

if __name__ == "__main__":
    cli()

