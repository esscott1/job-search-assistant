"""Entry point for LangGraph Studio / `langgraph dev` (see langgraph.json).

The dev server supplies its own checkpointer, so the graph is compiled without one.
"""

from .deps import real_deps
from .evaluate_graph import build_evaluate_graph

graph = build_evaluate_graph(real_deps())
