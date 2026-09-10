# GoonToThis

GoonToThis is a small Flask search interface that looks up movies and TV shows, then sends the selected TMDB title to an external watch site. It does not host, proxy, or download video.

## Run locally

1. Copy `.env.example` to `.env` and add your own TMDB API key for complete catalog search.
2. Run `./run-local.sh`.
3. Open <http://127.0.0.1:8002>.

The app can still use the configured 67movies semantic-search endpoint when no TMDB key is present, but a personal TMDB key is strongly recommended for complete, predictable results.

## Test

```sh
.venv/bin/python -m unittest discover -v
```

## Deploy

GitHub stores the source code; Render runs the Flask server. GitHub Pages cannot run this app by itself.

On Render, create a **Web Service** from the GitHub repository and use:

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn app:app`
- Health check path: `/healthz`

The included `Procfile` contains the same production start command. Configure secrets and deployment-specific values as Render environment variables; never commit `.env`.

Render's Free web service currently spins down after 15 minutes without inbound traffic and can take about a minute to wake. Its local filesystem is temporary, so search cache and local settings can disappear on a restart or redeploy. Use Supabase for settings that must persist.

Important variables:

- `TMDB_API_KEY`: your TMDB v3 API key.
- `MOVIE_SITE_BASE`: external watch-site origin; defaults to `https://67movies.net`.
- `SEARCH_FALLBACK_URL`: JSON catalog fallback; defaults to the 67movies semantic-search endpoint.
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, and `ADMIN_USER_IDS`: optional owner-panel configuration.
- `RENDER_API_KEY` and `RENDER_SERVICE_ID`, or `RESTART_WEBHOOK_URL`: optional restart control.

## Playback fallbacks and ads

67movies owns the playback page and its server selector, so server switching happens there after a title is opened. This app cannot reliably detect whether a cross-origin player fails after page load, nor can it safely remove or bypass ads injected by an external provider. Any ad-free option must be offered by the selected provider itself.

An independent whole-site fallback needs the fallback site's movie and TV URL formats—not only its hostname. For each additional site, record one working movie URL and one working TV episode URL before adding it.
