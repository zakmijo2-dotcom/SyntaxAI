"""Commands module for SyntaxAI."""

from .inspect import inspect_project
from .review import review_code
from .run import run_interactive, run_query

__all__ = ["run_interactive", "run_query", "inspect_project", "review_code"]
