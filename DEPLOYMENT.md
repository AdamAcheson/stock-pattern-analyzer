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
  entrypoint. It just imports the existing FastAPI `app`; every route
  keeps its real path (e.g. `/api/ohlcv`) since `backend/vercel.json`'s
  catch-all rewrite forwards every request to this one function and lets
  FastAPI's own router dispatch it.
- `backend/vercel.json` — the catch-all rewrite described above.
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
   in a browser — it should return `{"status":"ok"}`. If instead you get
   a 404, the rewrite destination in `backend/vercel.json` (`/api/index`)
   may need to change to `/api` — Vercel's exact function-naming
   convention for an `api/index.py` file wasn't something I could verify
   without a live deploy, so this is the one part of this setup most
   likely to need a one-line tweak after the first real deploy.
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

## Known risks worth watching after the first deploy

Two things here were reasoned about carefully but not verified against
real Vercel infrastructure, since this build environment has no way to
deploy to Vercel and test it directly:

- **Function timeout.** Vercel's Hobby-plan serverless functions default
  to a 10-second execution limit. This app's yfinance calls have been
  consistently fast in testing, but that testing happened from this
  build environment's network, not Vercel's — if a request to Yahoo
  Finance is ever slow from Vercel's infrastructure, an API call could
  time out (504) rather than just running long. Vercel's paid plans
  raise that limit if it becomes a real problem.
- **`curl_cffi` on Vercel's build image.** `data_fetch.py` depends on
  yfinance's `curl_cffi` backend (see BUILD_SPEC.md Stage 1 — it's what
  lets requests get through as a real browser TLS fingerprint instead of
  being blocked by Yahoo). `curl_cffi` ships precompiled native binaries
  per platform rather than being pure Python; it publishes Linux x86_64
  wheels so `pip install` on Vercel's build machine should pick up a
  compatible one, but that's an expectation based on how the package is
  distributed, not something confirmed by an actual deploy. If the
  backend's `/api/health` works but every other endpoint 500s, check the
  function logs for an import or native-library error here first.
