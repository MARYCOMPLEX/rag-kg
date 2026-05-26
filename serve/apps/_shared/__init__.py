"""Shared utilities for apps (api / worker / cli).

Apps can freely import from each other's _shared module.
This is the natural place for cross-app DI wiring and persistence adapters
that don't fit the strict packages/ dependency hierarchy.
"""
