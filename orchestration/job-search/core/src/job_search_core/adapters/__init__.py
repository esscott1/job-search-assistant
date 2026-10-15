"""Adapters implement the ports in `job_search_core.ports`.

Real adapters with heavy dependencies (anthropic, google) import them lazily, so the core
package and its tests work without those extras installed.
"""
