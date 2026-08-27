# Deploying to Vercel

This app deploys as **two separate Vercel projects from the same GitHub
repo** — one for the FastAPI backend, one for the React frontend — using
Vercel's "Root Directory" setting to point each project at its own
subfolder. This is deliberately simpler than combining them into one
project with a hand-rolled build config: each side gets Vercel's normal,
well-tested zero-config detection (Python serverless functions for
`backend/`, Vite static build for `frontend/`) instead of a custom
`builds`/`routes` setup that's easy to get subtly wrong and hard to debug
without live access to a deploy.

The tradeoff is two URLs instead of one, connected via CORS (already
configured in `backend/app/main.py`) rather than same-origin requests.

## What's already in the repo

- `backend/api/index.py` — the Vercel Python serverless function
  entrypoint. It just imports the existing FastAPI `app`; a single
  `api/index.py` exporting an ASGI app is Vercel's zero-config catch-all
  for everything under `/api/*`, receiving the real incoming path as-is,
  so every route keeps working exactly as declared (e.g. `/api/ohlcv`)
  with no rewrite or re-declaration needed. (An earlier version of this
  file shipped with a `backend/vercel.json` rewrite that overwrote every
  request's path with a fixed string, breaking every route — caught by
  testing a real deploy and seeing FastAPI's own 404 come back for
  every single path. Removed; there's no `vercel.json` in `backend/`
  anymore.)
- `backend/requirements.txt` — trimmed to only what the app imports
  (matplotlib, used solely by the dev-only `render_pattern_chart.py`
  verification script, moved to `backend/requirements-dev.txt` so it
  doesn't bloat the deployed function).
- CORS in `backend/app/main.py` already allows `https://*.vercel.app`
  (covers the production domain and every preview-deployment URL) plus
  an optional `FRONTEND_ORIGIN` environment variable for a custom domain
  later.
- The frontend already reads its API base URL from the
  `VITE_API_BASE_URL` environment variable (`frontend/src/lib/api.ts`),
  falling back to `http://localhost:8000` for local dev. **This must be
  set in the frontend's Vercel project once the backend has a URL** (step
  4 below) — if it's left unset, the deployed frontend will try to call
  `localhost` from visitors' browsers and every request will fail.

## Steps (done once, in the Vercel dashboard)

1. **Deploy the backend.** In [vercel.com/adamachesons-projects](https://vercel.com/adamachesons-projects):
   Add New → Project → import `AdamAcheson/stock-pattern-analyzer` →
   set **Root Directory** to `backend` → deploy. Vercel should
   auto-detect it as a Python project from `requirements.txt`; no
   framework preset or build command should be needed.
2. **Verify it.** Once deployed, hit `https://<backend-project>.vercel.app/api/health`
   in a browser — it should return `{"status":"ok"}`. Note that Vercel's
   preview deployments (anything not on the production branch) require
   you to be logged into Vercel to view them at all — an unauthenticated
   request gets redirected rather than seeing the app's response, which
   isn't a bug, just Deployment Protection. Test from a browser tab
   where you're already logged in.
3. **Deploy the frontend.** Add New → Project → import the same repo
   again → set **Root Directory** to `frontend` this time → Vercel
   should auto-detect Vite → deploy.
4. **Connect them.** In the frontend project's Settings → Environment
   Variables, add `VITE_API_BASE_URL` = `https://<backend-project>.vercel.app`
   (the URL from step 1, no trailing slash) → redeploy the frontend so
   the build picks up the new env var (Vite inlines env vars at build
   time, not runtime).
5. **Smoke-test the real thing:** open the frontend's URL, enter a
   ticker, confirm the chart/patterns/summary all load. Check the
   browser's console for any CORS or network errors — if the backend's
   actual domain doesn't match the `*.vercel.app` CORS pattern for some
   reason (e.g. a custom domain is attached later), set `FRONTEND_ORIGIN`
   in the **backend** project's environment variables to the frontend's
   exact origin and redeploy.

After this one-time setup, every push to the connected branch
auto-deploys both projects independently — no further manual steps.

## Known risks

- **`curl_cffi` on Vercel's build image — CONFIRMED WORKING (2026-08-27).**
  `data_fetch.py` depends on yfinance's `curl_cffi` backend (see
  BUILD_SPEC.md Stage 1), which ships precompiled native binaries rather
  than being pure Python. This was flagged here as unverified until a
  real deploy confirmed `app.main` (and everything it imports,
  `data_fetch.py` included) loads successfully on Vercel's Python
  runtime — the first real deploy returned a FastAPI-generated response
  rather than an import-time crash, which only happens if every import
  in that chain resolved.
- **Function timeout — still unverified.** Vercel's Hobby-plan serverless
  functions default to a 10-second execution limit. This app's yfinance
  calls have been consistently fast in testing, but that testing
  happened from this build environment's network, not Vercel's — if a
  request to Yahoo Finance is ever slow from Vercel's infrastructure, an
  API call could time out (504) rather than just running long. This
  needs an endpoint that actually calls yfinance (e.g. `/api/ohlcv`) to
  test, not just `/api/health`. Vercel's paid plans raise that limit if
  it becomes a real problem.
