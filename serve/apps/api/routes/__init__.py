"""API route modules — auto-discovery registry.

Each `routes/<name>.py` exposes a top-level `router: APIRouter`. New M7
modules add themselves to `M7_ROUTES`; the FastAPI app picks them up
when present, silently skips if not yet implemented (during parallel
agent rollout).
"""

from __future__ import annotations

from importlib import import_module

from fastapi import APIRouter

# Routes already shipped (M1–M6):
M0_M6_ROUTES: tuple[str, ...] = (
    "libraries",
    "conversations",
)

# Routes added in M7 — see BACKEND_ROADMAP §4 + ADR review:
M7_ROUTES: tuple[str, ...] = (
    "frontend_libraries",  # frontend /api adapter for integration
    "tasks",  # ADR-0009
    "notifications",  # ADR-0011
    "activity",  # ADR-0014
    "library_settings",  # ADR-0012
    "eval",  # ADR-0016 + 0021
    "feedback",  # ADR-0016
    "search",  # ADR-0023
    "documents",  # M4 detail drawer
    "ingest",  # ADR-0019
    "review",  # M5 review with citation_style + estimate
)


def collect_routers() -> list[APIRouter]:
    """Collect every route module that has been implemented.

    Modules absent from disk (during phased rollout) are silently skipped.
    A module that fails to import for any other reason will surface the
    error — we do NOT swallow programming bugs.
    """
    routers: list[APIRouter] = []
    for name in (*M0_M6_ROUTES, *M7_ROUTES):
        try:
            mod = import_module(f"apps.api.routes.{name}")
        except ModuleNotFoundError as exc:
            # Only skip if the missing module IS the route file itself
            if exc.name == f"apps.api.routes.{name}":
                continue
            raise  # downstream import error — surface it
        router = getattr(mod, "router", None)
        if isinstance(router, APIRouter):
            routers.append(router)
    return routers
