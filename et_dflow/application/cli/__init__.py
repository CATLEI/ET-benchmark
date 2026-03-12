"""
Command-line interface.

Contains CLI tools, configuration wizard, and simple mode.
"""

# Import cli function from the parent cli.py module
# This allows et_dflow.application.cli.main to import cli
import sys
from pathlib import Path

# Import from parent directory's cli.py
parent_dir = Path(__file__).parent.parent
cli_file = parent_dir / "cli.py"

# Read and execute the cli.py file to get the cli function
if cli_file.exists():
    import importlib.util
    spec = importlib.util.spec_from_file_location("et_dflow.application.cli_module", cli_file)
    cli_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli_module)
    cli = cli_module.cli
else:
    # Fallback: define a dummy cli if file not found
    def cli():
        """CLI not available."""
        pass

