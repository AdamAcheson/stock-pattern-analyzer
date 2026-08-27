"""Vercel Python serverless function entrypoint.

Vercel auto-detects any file under api/ that exports an ASGI app named
`app` and serves it as a serverless function. Every route in
app.main is already declared with its full path (e.g. "/api/ohlcv"),
so vercel.json's catch-all rewrite forwards every request straight to
this one function, and FastAPI's own router does the rest -- no route
re-declaration needed here.
"""

from app.main import app  # noqa: F401
