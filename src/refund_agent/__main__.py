"""Allow the package to run with ``python -m refund_agent``."""

from .cli import main

raise SystemExit(main())
