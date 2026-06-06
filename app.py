"""
GoonToThis - PlayIMDb link implementation.
"""

import json
import os
import re
import threading
import time
from urllib.parse import quote, urlencode

import requests
from flask import Flask, abort, redirect, render_template, request, send_from_directory

app = Flask(__name__)

PLAY_IMDB_TITLE_BASE = "https://playimdb.com/title"
CACHE_PATH = os.environ.get("CACHE_PATH", "/tmp/movis-cache.json")
CACHE_SCHEMA_VERSION = 1
CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", str(60 * 60 * 24)))
CACHE_MAX_ENTRIES = int(os.environ.get("CACHE_MAX_ENTRIES", "500"))
MAX_QUERY_LENGTH = 120
IMDB_ID_RE = re.compile(r"^tt\d+$")

SITE_NAME = "GoonToThis"
SITE_TITLE = "GoonToThis - Goon To This Movie Search"
SITE_URL = "https://goontothis.com"
SITE_DESCRIPTION = "Search a movie or show, then tap a card to go right to it."

GOATCOUNTER_SRC = "//gc.zgo.at/count.js"
GOATCOUNTER_SITE = "https://goon2this.goatcounter.com/count"
OG_IMAGE = f"{SITE_URL}/static/og-image.png"


def now_ts():
    return int(time.time())


def cache_entry(value, timestamp=None):
    timestamp = timestamp or now_ts()
    return {
        "value": value,
        "created_at": timestamp,
        "last_accessed_at": timestamp,
        "expires_at": timestamp + CACHE_TTL_SECONDS,
    }


def normalize_cache(raw):
    if not isinstance(raw, dict):
        return {"version": CACHE_SCHEMA_VERSION, "entries": {}}

    if raw.get("version") == CACHE_SCHEMA_VERSION and isinstance(raw.get("entries"), dict):
        return raw

    timestamp = now_ts()
    entries = {}
    for key, value in raw.items():
        if key.startswith("s_") and isinstance(value, list):
            entries[key] = cache_entry(value, timestamp)

    return {"version": CACHE_SCHEMA_VERSION, "entries": entries}


def load_cache():
    try:
        with open(CACHE_PATH) as fh:
            return normalize_cache(json.load(fh))
    except Exception:
        return normalize_cache({})


cache = load_cache()
cache_lock = threading.RLock()


def prune_cache():
    entries = cache.setdefault("entries", {})
    timestamp = now_ts()
    expired = [
        key for key, entry in entries.items()
        if not isinstance(entry, dict) or entry.get("expires_at", 0) <= timestamp
    ]
    for key in expired:
        entries.pop(key, None)

    if len(entries) <= CACHE_MAX_ENTRIES:
        return

    ordered = sorted(
        entries.items(),
        key=lambda item: item[1].get("last_accessed_at", item[1].get("created_at", 0)),
    )
    for key, _entry in ordered[:len(entries) - CACHE_MAX_ENTRIES]:
        entries.pop(key, None)


def save_cache():
    directory = os.path.dirname(CACHE_PATH)
    tmp_path = f"{CACHE_PATH}.tmp"

    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(tmp_path, "w") as fh:
            json.dump(cache, fh, separators=(",", ":"))
        os.replace(tmp_path, CACHE_PATH)
    except Exception:
        pass


def valid_imdb_id(imdb_id):
    return bool(IMDB_ID_RE.fullmatch(imdb_id or ""))


def play_url(imdb_id):
    return f"{PLAY_IMDB_TITLE_BASE}/{imdb_id}/"


def with_play_urls(results):
    hydrated = []
    for item in results:
        imdb_id = item.get("id", "")
        if not valid_imdb_id(imdb_id):
            continue
        hydrated.append({**item, "play_url": play_url(imdb_id)})
    return hydrated


def search_cache_key(query):
    return "s_" + query.lower().strip()


def cached_search(key):
    with cache_lock:
        prune_cache()
        entry = cache.setdefault("entries", {}).get(key)
        if not entry:
            return None
        entry["last_accessed_at"] = now_ts()
        return with_play_urls(entry.get("value", []))


def remember_search(key, results):
    if not results:
        return
    with cache_lock:
        cache.setdefault("entries", {})[key] = cache_entry(results)
        prune_cache()
        save_cache()


def template_context(**extra):
    page_title = extra.pop("page_title", SITE_TITLE)
    page_description = extra.pop("page_description", SITE_DESCRIPTION)
    canonical_url = extra.pop("canonical_url", f"{SITE_URL}/")
    base = {
        "site_name": SITE_NAME,
        "site_title": page_title,
        "site_url": SITE_URL,
        "site_description": page_description,
        "canonical_url": canonical_url,
        "og_image": extra.pop("og_image", OG_IMAGE),
        "goatcounter_src": GOATCOUNTER_SRC,
        "goatcounter_site": GOATCOUNTER_SITE,
    }
    base.update(extra)
    return base


def search_imdb(query):
    normalized_query = query.strip()[:MAX_QUERY_LENGTH]
    key = search_cache_key(normalized_query)
    cached = cached_search(key)
    if cached is not None:
        return cached

    q = quote(normalized_query.lower())
    ch = normalized_query[0].lower() if normalized_query else "a"
    if not ch.isalnum():
        ch = "a"

    try:
        res = requests.get(
            f"https://v2.sg.media-imdb.com/suggestion/{ch}/{q}.json",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        app.logger.warning("Search failed for %r: %s", normalized_query, e)
        return []

    results = []
    for item in data.get("d", []):
        imdb_id = item.get("id", "")
        if not valid_imdb_id(imdb_id):
            continue

        img = item.get("i", {})
        media_type = item.get("q", "")
        results.append({
            "id": imdb_id,
            "title": item.get("l", ""),
            "year": str(item.get("y", "")),
            "poster": img.get("imageUrl", "") if isinstance(img, dict) else "",
            "type": media_type,
            "is_tv": "series" in media_type.lower() or "mini" in media_type.lower(),
            "play_url": play_url(imdb_id),
        })

    remember_search(key, results)

    return with_play_urls(results)


@app.route("/")
def home():
    return render_template("home.html", **template_context())


@app.route("/favicon.png")
def favicon_png():
    return send_from_directory(app.root_path, "favicon.png", mimetype="image/png")


@app.route("/favicon.ico")
def favicon_ico():
    return redirect("/favicon.png")


@app.route("/cut2.mp3")
def cut2_mp3():
    return send_from_directory(app.root_path, "CUT2.mp3", mimetype="audio/mpeg")


@app.route("/healthz")
def healthz():
    return {"ok": True, "site": SITE_NAME}


@app.route("/robots.txt")
def robots_txt():
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {SITE_URL}/sitemap.xml",
        "",
    ]
    return app.response_class("\n".join(lines), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_xml():
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE_URL}/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""
    return app.response_class(xml, mimetype="application/xml")


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()[:MAX_QUERY_LENGTH]
    if not q:
        return redirect("/")

    query_path = "/search?" + urlencode({"q": q})
    page_title = f'"{q}" results - {SITE_NAME}'
    page_description = f'Search results for "{q}". Swipe the cards and launch a movie or show fast.'

    return render_template(
        "results.html",
        **template_context(
            q=q,
            results=search_imdb(q),
            page_title=page_title,
            page_description=page_description,
            canonical_url=f"{SITE_URL}{query_path}",
        ),
    )


@app.route("/play/<imdb_id>")
def play(imdb_id):
    if not valid_imdb_id(imdb_id):
        abort(404)
    return redirect(play_url(imdb_id))


@app.route("/tv/<imdb_id>")
def tv_detail(imdb_id):
    if not valid_imdb_id(imdb_id):
        abort(404)
    return redirect(play_url(imdb_id))


@app.route("/watch-tv/<imdb_id>/<int:season>/<int:episode>")
def watch_tv(imdb_id, season, episode):
    if not valid_imdb_id(imdb_id):
        abort(404)
    return redirect(play_url(imdb_id))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
