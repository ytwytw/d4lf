"""Command-line entry point for the public repository safety gate."""

import sys

from src.tools.public_safety.cli import main

sys.exit(main())
