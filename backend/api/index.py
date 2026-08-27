"""Vercel Python serverless function entrypoint.

A single file at api/index.py exporting an ASGI `app` is Vercel's
zero-config catch-all for every request under /api/* -- it receives the
real incoming path (e.g. "/api/ohlcv") as-is, and FastAPI's own router
dispatches from there. No vercel.json is needed for this: an earlier
version of this file added a custom rewrite to "/api/index", which
overwrote every request's path with that literal string before FastAPI
ever saw it, so every route 404'd against a path nothing was registered
at. Caught by testing an actual deploy, not by re-reading the config.
"""

from app.main import app  # noqa: F401
