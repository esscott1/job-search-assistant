"""Framework-free business logic for the job-search workflow.

Nothing in this package may import an orchestration framework (LangGraph, LangChain,
Temporal, an agent SDK, ...). Orchestration approaches live in ../approaches and call
into this package. `core/tests/test_import_boundary.py` enforces the rule in CI.
"""

__version__ = "0.1.0"
