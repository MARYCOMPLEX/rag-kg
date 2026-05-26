"""Concrete adapters for the orchestration package.

Implementations of the Protocols declared in `packages/orchestration/queue.py`,
`packages/orchestration/notifications.py`, etc. Lives outside `service.py`
per CODING_STANDARDS §3 — only adapters import third-party SDKs (Arq,
redis.asyncio, sqlalchemy).
"""
