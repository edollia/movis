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
from flask import Flask, abort, jsonify, redirect, render_template, request, send_from_directory

app = Flask(__name__)

PLAY_IMDB_TITLE_BASE = "https://playimdb.com/title"
CACHE_PATH = os.environ.get("CACHE_PATH", "/tmp/movis-cache.json")
SETTINGS_PATH = os.environ.get("SETTINGS_PATH", os.path.join(app.root_path, ".runtime", "settings.json"))
CACHE_SCHEMA_VERSION = 1
MAX_QUERY_LENGTH = 120
IMDB_ID_RE = re.compile(r"^tt\d+$")

SITE_NAME = "GoonToThis"
SITE_TITLE = "GoonToThis - Goon To This Movie Search"
SITE_URL = "https://goontothis.com"
SITE_DESCRIPTION = "Search a movie or show, then tap a card to go right to it."

GOATCOUNTER_SRC = "//gc.zgo.at/count.js"
GOATCOUNTER_SITE = "https://goon2this.goatcounter.com/count"
OG_IMAGE = f"{SITE_URL}/static/og-image.png"


@app.after_request
def add_cache_headers(response):
    if response.content_type and response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    return response

DEFAULT_SITE_SETTINGS = {
    "show_loading_screen": True,
    "loading_line_1": "Knock, knock, Neo.",
    "loading_line_2": "Have you gooned today?",
    "show_signal_support": True,
    "support_label": "support",
    "support_handle": "@pawswirl",
    "support_url": "https://www.instagram.com/pawswirl/",
}

DEFAULT_SUPABASE_URL = "https://vmzovzgynijvpemcirqb.supabase.co"
DEFAULT_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_l-sNpT6S5tP8U1pPeJfgzQ_HMTlNPSS"

SUPABASE_URL = (
    os.environ.get("SUPABASE_URL")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_URL")
    or DEFAULT_SUPABASE_URL
).rstrip("/")
SUPABASE_ANON_KEY = (
    os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    or DEFAULT_SUPABASE_PUBLISHABLE_KEY
)
DEFAULT_ADMIN_USER_ID = "f7f96a98-985d-402f-9233-9cd0bc0439ce"
ADMIN_USER_IDS = {
    user_id.strip().lower()
    for user_id in os.environ.get("ADMIN_USER_IDS", DEFAULT_ADMIN_USER_ID).split(",")
    if user_id.strip()
}
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "").strip()
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "").strip()
RESTART_WEBHOOK_URL = (
    os.environ.get("RESTART_WEBHOOK_URL")
    or os.environ.get("RENDER_DEPLOY_HOOK_URL")
    or ""
).strip()
RESTART_WEBHOOK_METHOD = os.environ.get("RESTART_WEBHOOK_METHOD", "POST").strip().upper() or "POST"
RESTART_WEBHOOK_TOKEN = os.environ.get("RESTART_WEBHOOK_TOKEN", "").strip()


def env_int(name, default):
    try:
        value = int(os.environ.get(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


CACHE_TTL_SECONDS = env_int("CACHE_TTL_SECONDS", 60 * 60 * 24)
CACHE_MAX_ENTRIES = env_int("CACHE_MAX_ENTRIES", 500)
SETTINGS_CACHE_TTL_SECONDS = env_int("SETTINGS_CACHE_TTL_SECONDS", 15)


def now_ts():
    return int(time.time())


settings_lock = threading.RLock()
settings_cache = {
    "value": DEFAULT_SITE_SETTINGS.copy(),
    "loaded_at": 0,
}


def bool_setting(value, default):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def text_setting(value, default, max_length):
    if not isinstance(value, str):
        value = default
    value = value.strip()
    return (value or default)[:max_length]


def url_setting(value, default):
    value = text_setting(value, default, 300)
    if not value.startswith(("https://", "http://")):
        return default
    return value


def normalize_settings(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "show_loading_screen": bool_setting(
            raw.get("show_loading_screen"),
            DEFAULT_SITE_SETTINGS["show_loading_screen"],
        ),
        "loading_line_1": text_setting(
            raw.get("loading_line_1"),
            DEFAULT_SITE_SETTINGS["loading_line_1"],
            80,
        ),
        "loading_line_2": text_setting(
            raw.get("loading_line_2"),
            DEFAULT_SITE_SETTINGS["loading_line_2"],
            80,
        ),
        "show_signal_support": bool_setting(
            raw.get("show_signal_support"),
            DEFAULT_SITE_SETTINGS["show_signal_support"],
        ),
        "support_label": text_setting(
            raw.get("support_label"),
            DEFAULT_SITE_SETTINGS["support_label"],
            28,
        ),
        "support_handle": text_setting(
            raw.get("support_handle"),
            DEFAULT_SITE_SETTINGS["support_handle"],
            42,
        ),
        "support_url": url_setting(
            raw.get("support_url"),
            DEFAULT_SITE_SETTINGS["support_url"],
        ),
    }


def supabase_configured():
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY)


def supabase_headers(token=None, prefer=None):
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {token or SUPABASE_ANON_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def load_local_settings():
    try:
        with open(SETTINGS_PATH) as fh:
            return normalize_settings(json.load(fh))
    except Exception:
        return DEFAULT_SITE_SETTINGS.copy()


def save_local_settings(settings):
    directory = os.path.dirname(SETTINGS_PATH)
    tmp_path = f"{SETTINGS_PATH}.tmp"
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(tmp_path, "w") as fh:
        json.dump(normalize_settings(settings), fh, separators=(",", ":"))
    os.replace(tmp_path, SETTINGS_PATH)


def remember_local_settings(settings):
    try:
        save_local_settings(settings)
    except Exception as e:
        app.logger.warning("Could not write local settings fallback: %s", e)


def load_supabase_settings():
    if not supabase_configured():
        return None

    res = requests.get(
        f"{SUPABASE_URL}/rest/v1/movis_settings",
        params={
            "key": "eq.site",
            "select": (
                "show_loading_screen,loading_line_1,loading_line_2,"
                "show_signal_support,support_label,support_handle,support_url"
            ),
            "limit": "1",
        },
        headers=supabase_headers(),
        timeout=5,
    )
    res.raise_for_status()
    data = res.json()
    if not data:
        return None
    return normalize_settings(data[0])


def get_site_settings(force=False):
    with settings_lock:
        timestamp = now_ts()
        if not force and timestamp - settings_cache["loaded_at"] < SETTINGS_CACHE_TTL_SECONDS:
            return settings_cache["value"].copy()

        settings = load_local_settings()
        if supabase_configured():
            try:
                remote_settings = load_supabase_settings()
                if remote_settings:
                    settings = remote_settings
                    remember_local_settings(settings)
            except Exception as e:
                app.logger.warning("Could not load Supabase settings: %s", e)

        settings_cache["value"] = normalize_settings(settings)
        settings_cache["loaded_at"] = timestamp
        return settings_cache["value"].copy()


def save_site_settings(settings, admin_token=None):
    settings = normalize_settings(settings)

    if supabase_configured():
        payload = {"key": "site", **settings}
        res = requests.post(
            f"{SUPABASE_URL}/rest/v1/movis_settings",
            params={"on_conflict": "key"},
            headers=supabase_headers(admin_token, prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
            timeout=8,
        )
        res.raise_for_status()

    with settings_lock:
        remember_local_settings(settings)
        settings_cache["value"] = settings.copy()
        settings_cache["loaded_at"] = now_ts()

    return settings.copy()


def admin_config():
    return {
        "enabled": supabase_configured(),
        "supabaseUrl": SUPABASE_URL,
        "supabaseAnonKey": SUPABASE_ANON_KEY,
    }


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
        if not isinstance(item, dict):
            continue
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
    with cache_lock:
        cache.setdefault("entries", {})[key] = cache_entry(results)
        prune_cache()
        save_cache()


def bearer_token():
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def admin_error(message, status=401):
    return no_store_json({"ok": False, "error": message}, status)


def supabase_user(token):
    if not supabase_configured():
        return None

    res = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers=supabase_headers(token),
        timeout=8,
    )
    if res.status_code != 200:
        return None
    return res.json()


def user_is_admin(user):
    user_id = user.get("id") if isinstance(user, dict) else ""
    return bool(user_id and user_id.lower() in ADMIN_USER_IDS)


def require_admin():
    token = bearer_token()
    if not token:
        return None, None, admin_error("Sign in first.", 401)
    user = supabase_user(token)
    if not user:
        return None, None, admin_error("Your session expired. Sign in again.", 401)
    if not user_is_admin(user):
        return None, None, admin_error("This Supabase user is not an admin.", 403)
    return user, token, None


def clear_search_cache():
    global cache
    with cache_lock:
        cleared = len(cache.get("entries", {}))
        cache = normalize_cache({})
        save_cache()
    return cleared


def trigger_restart():
    if RENDER_API_KEY and RENDER_SERVICE_ID:
        res = requests.post(
            f"https://api.render.com/v1/services/{RENDER_SERVICE_ID}/restart",
            headers={
                "Authorization": f"Bearer {RENDER_API_KEY}",
                "Accept": "application/json",
            },
            timeout=15,
        )
        if res.status_code >= 400:
            return False, f"Render restart returned HTTP {res.status_code}."
        return True, "Render restart requested."

    if not RESTART_WEBHOOK_URL:
        return False, "Restart hook is not configured."

    headers = {}
    if RESTART_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Bearer {RESTART_WEBHOOK_TOKEN}"

    res = requests.request(
        RESTART_WEBHOOK_METHOD,
        RESTART_WEBHOOK_URL,
        headers=headers,
        timeout=10,
    )
    if res.status_code >= 400:
        return False, f"Restart hook returned HTTP {res.status_code}."
    return True, "Restart hook fired."


def no_store_json(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def template_context(**extra):
    page_title = extra.pop("page_title", SITE_TITLE)
    page_description = extra.pop("page_description", SITE_DESCRIPTION)
    canonical_url = extra.pop("canonical_url", f"{SITE_URL}/")
    settings = extra.pop("settings", get_site_settings())
    base = {
        "site_name": SITE_NAME,
        "site_title": page_title,
        "site_url": SITE_URL,
        "site_description": page_description,
        "canonical_url": canonical_url,
        "og_image": extra.pop("og_image", OG_IMAGE),
        "goatcounter_src": GOATCOUNTER_SRC,
        "goatcounter_site": GOATCOUNTER_SITE,
        "settings": settings,
        "admin_config": admin_config(),
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
    if not ch.isascii() or not ch.isalnum():
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


@app.route("/api/admin/settings", methods=["GET", "POST"])
def admin_settings():
    user, token, error = require_admin()
    if error:
        return error

    if request.method == "GET":
        return no_store_json({
            "ok": True,
            "email": user.get("email"),
            "settings": get_site_settings(force=True),
            "restart_configured": bool((RENDER_API_KEY and RENDER_SERVICE_ID) or RESTART_WEBHOOK_URL),
        })

    payload = request.get_json(silent=True) or {}
    merged = get_site_settings(force=True)
    merged.update(payload)

    try:
        settings = save_site_settings(merged, admin_token=token)
    except Exception as e:
        app.logger.warning("Could not save admin settings: %s", e)
        return no_store_json({"ok": False, "error": "Could not save settings."}, 502)

    return no_store_json({"ok": True, "settings": settings})


@app.route("/api/admin/cache/clear", methods=["POST"])
def admin_clear_cache():
    _user, _token, error = require_admin()
    if error:
        return error

    cleared = clear_search_cache()
    return no_store_json({"ok": True, "cleared": cleared})


@app.route("/api/admin/server/restart", methods=["POST"])
def admin_restart_server():
    _user, _token, error = require_admin()
    if error:
        return error

    ok, message = trigger_restart()
    return no_store_json({"ok": ok, "message": message}, 200 if ok else 503)


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
