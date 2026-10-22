"""Entry point for LangGraph Studio / `langgraph dev` (see langgraph.json).

`make_graph` is a graph factory: the server calls it when it needs the graph, so importing this
module opens no tracker and makes no client. The dependencies are built once, on first use, in a
worker thread, because opening the SQLite tracker is blocking I/O and the server calls factories
on its event loop. The dev server supplies its own checkpointer, so the graph is compiled without
one.
"""

import asyncio
from functools import cache

# Absolute imports: the server loads this file by path, not as part of the package.
from job_search_langgraph.deps import Deps, real_deps
from job_search_langgraph.evaluate_graph import build_evaluate_graph


@cache
def _deps() -> Deps:
    return real_deps()


async def make_graph(config=None):
    return build_evaluate_graph(await asyncio.to_thread(_deps))
