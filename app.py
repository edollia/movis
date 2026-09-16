"""GoonToThis search and in-site player application."""

import json
import os
import re
import secrets
import threading
import time
from urllib.parse import urlencode, urlsplit

import requests
from flask import Flask, abort, g, jsonify, redirect, render_template, request, send_from_directory

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024


def validated_http_url(value, name="URL", *, origin_only=False):
    if not isinstance(value, str):
        raise RuntimeError(f"{name} must be a URL string.")
    value = value.strip()
    if not value:
        return ""
    if re.search(r"[\x00-\x20\x7f]", value):
        raise RuntimeError(f"{name} cannot contain whitespace or control characters.")

    try:
        parsed = urlsplit(value)
        hostname = parsed.hostname
        parsed.port
    except ValueError as exc:
        raise RuntimeError(f"{name} is not a valid URL.") from exc

    local_http = parsed.scheme == "http" and hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not local_http:
        raise RuntimeError(f"{name} must use HTTPS (HTTP is allowed only for localhost).")
    if not hostname or parsed.username or parsed.password or parsed.fragment:
        raise RuntimeError(f"{name} must be an absolute URL without credentials or a fragment.")
    if origin_only and (parsed.query or parsed.path not in {"", "/"}):
        raise RuntimeError(f"{name} must contain only an origin, without a path or query.")

    if origin_only:
        return f"{parsed.scheme}://{parsed.netloc}"
    return value


def configured_http_url(name, default, *, origin_only=False):
    """Validate operator-controlled outbound URLs once, at process startup."""
    return validated_http_url(os.environ.get(name, default), name, origin_only=origin_only)


MOVIE_SITE_BASE = configured_http_url(
    "MOVIE_SITE_BASE",
    "https://67movies.net",
    origin_only=True,
)
VIDLOVE_PLAYER_ORIGIN = "https://player.vidlove.cc"
VIDLOVE_API_ORIGIN = "https://api.vidlove.cc"
TMDB_API_BASE = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
# Same browser-visible TMDB v3 key used by the owned 67movies search client.
# Operators can replace it with an environment value without changing code.
TMDB_API_KEY = os.environ.get(
    "TMDB_API_KEY",
    "a46c50a0ccb1bafe2b15665df7fad7e1",
).strip() or "a46c50a0ccb1bafe2b15665df7fad7e1"
SEARCH_FALLBACK_URL = configured_http_url(
    "SEARCH_FALLBACK_URL",
    f"{MOVIE_SITE_BASE}/api/semantic-search",
)
CACHE_PATH = os.environ.get("CACHE_PATH", "/tmp/movis-cache.json")
SETTINGS_PATH = os.environ.get("SETTINGS_PATH", os.path.join(app.root_path, ".runtime", "settings.json"))
CACHE_SCHEMA_VERSION = 4
MAX_CACHE_FILE_BYTES = 25 * 1024 * 1024
MAX_CATALOG_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_QUERY_LENGTH = 120
MAX_SEARCH_RESULTS = 50
MAX_TITLE_LENGTH = 240
MAX_SEASON_NUMBER = 999
MAX_EPISODE_NUMBER = 9999
TMDB_ID_RE = re.compile(r"^[1-9]\d{0,9}$")
TMDB_POSTER_PATH_RE = re.compile(r"^/[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")

SITE_NAME = "GoonToThis"
SITE_TITLE = "GoonToThis - Movies"
SITE_URL = "https://goontothis.com"
SITE_DESCRIPTION = (
    "Search any movie or show and jump straight to the highest-quality video "
    "experience available across movie websites."
)

GOATCOUNTER_SRC = "https://gc.zgo.at/count.js"
GOATCOUNTER_SITE = "https://goon2this.goatcounter.com/count"
OG_IMAGE = f"{SITE_URL}/static/og-image.png"


@app.before_request
def create_csp_nonce():
    g.csp_nonce = secrets.token_urlsafe(18)


@app.after_request
def add_cache_headers(response):
    if response.content_type and response.content_type.startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = (
        'camera=(), microphone=(), geolocation=(), fullscreen=(self "https://player.vidlove.cc")'
    )
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
    if request.is_secure:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    connect_sources = ["'self'", "https://goon2this.goatcounter.com"]
    if SUPABASE_URL:
        connect_sources.append(SUPABASE_URL)
    player_endpoints = {"watch_tv", "watch_movie"}
    frame_src = f"frame-src {VIDLOVE_PLAYER_ORIGIN}" if request.endpoint in player_endpoints else "frame-src 'none'"
    response.headers["Content-Security-Policy"] = "; ".join([
        "default-src 'self'",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        frame_src,
        "form-action 'self'",
        f"script-src 'self' 'nonce-{g.csp_nonce}' https://gc.zgo.at https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
        "font-src https://fonts.gstatic.com",
        "img-src 'self' data: https://image.tmdb.org",
        "media-src 'self'",
        f"connect-src {' '.join(connect_sources)}",
    ])
    return response

DEFAULT_SITE_SETTINGS = {
    "show_loading_screen": True,
    "loading_line_1": "uhhh",
    "loading_line_2": "hi.",
    "show_signal_support": True,
    "support_label": "support",
    "support_handle": "@pawswirl",
    "support_url": "https://www.instagram.com/pawswirl/",
}

SUPABASE_URL = configured_http_url(
    "SUPABASE_URL",
    os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""),
    origin_only=True,
)
SUPABASE_ANON_KEY = (
    os.environ.get("SUPABASE_ANON_KEY")
    or os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    or os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY")
    or ""
)
ADMIN_USER_IDS = {
    user_id.strip().lower()
    for user_id in os.environ.get("ADMIN_USER_IDS", "").split(",")
    if user_id.strip()
}
RENDER_API_KEY = os.environ.get("RENDER_API_KEY", "").strip()
RENDER_SERVICE_ID = os.environ.get("RENDER_SERVICE_ID", "").strip()
RESTART_WEBHOOK_URL = configured_http_url(
    "RESTART_WEBHOOK_URL",
    os.environ.get("RENDER_DEPLOY_HOOK_URL", ""),
)
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
METADATA_CACHE_TTL_SECONDS = env_int("METADATA_CACHE_TTL_SECONDS", 60 * 60 * 6)


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
    try:
        return validated_http_url(value, "support_url")
    except RuntimeError:
        return default


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
        entries = {}
        for key, entry in raw["entries"].items():
            if (
                not isinstance(key, str)
                or not key.startswith("s_")
                or len(key) > MAX_QUERY_LENGTH + 2
                or not isinstance(entry, dict)
                or not isinstance(entry.get("value"), list)
            ):
                continue
            timestamps = (
                entry.get("created_at"),
                entry.get("last_accessed_at"),
                entry.get("expires_at"),
            )
            if not all(isinstance(value, int) and not isinstance(value, bool) for value in timestamps):
                continue
            entries[key] = {
                "value": entry["value"][:MAX_SEARCH_RESULTS],
                "created_at": timestamps[0],
                "last_accessed_at": timestamps[1],
                "expires_at": timestamps[2],
            }
            if len(entries) >= CACHE_MAX_ENTRIES:
                break
        return {"version": CACHE_SCHEMA_VERSION, "entries": entries}

    timestamp = now_ts()
    entries = {}
    for key, value in raw.items():
        if (
            isinstance(key, str)
            and key.startswith("s_")
            and len(key) <= MAX_QUERY_LENGTH + 2
            and isinstance(value, list)
        ):
            entries[key] = cache_entry(value[:MAX_SEARCH_RESULTS], timestamp)
            if len(entries) >= CACHE_MAX_ENTRIES:
                break

    return {"version": CACHE_SCHEMA_VERSION, "entries": entries}


def load_cache():
    try:
        if os.path.getsize(CACHE_PATH) > MAX_CACHE_FILE_BYTES:
            app.logger.warning("Ignoring oversized search cache at %s", CACHE_PATH)
            return normalize_cache({})
        with open(CACHE_PATH) as fh:
            return normalize_cache(json.load(fh))
    except Exception:
        return normalize_cache({})


cache = load_cache()
cache_lock = threading.RLock()
metadata_cache = {}
metadata_cache_lock = threading.RLock()


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
    tmp_path = f"{CACHE_PATH}.{os.getpid()}.{threading.get_ident()}.tmp"

    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(tmp_path, "w") as fh:
            json.dump(cache, fh, separators=(",", ":"))
        os.replace(tmp_path, CACHE_PATH)
    except Exception:
        pass


def normalized_query(value):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    return " ".join(value.split())[:MAX_QUERY_LENGTH].strip()


def metadata_text(value, max_length=MAX_TITLE_LENGTH):
    if not isinstance(value, str):
        return ""
    value = re.sub(r"[\x00-\x1f\x7f]+", " ", value)
    return " ".join(value.split())[:max_length].strip()


def poster_url_from_path(value):
    if not isinstance(value, str) or not TMDB_POSTER_PATH_RE.fullmatch(value):
        return ""
    if "//" in value or "/../" in value:
        return ""
    return f"{TMDB_IMAGE_BASE}{value}"


def normalized_poster_url(value):
    if not isinstance(value, str):
        return ""
    prefix = f"{TMDB_IMAGE_BASE}/"
    if not value.startswith(prefix):
        return ""
    return poster_url_from_path(value[len(TMDB_IMAGE_BASE):])


def valid_tmdb_id(tmdb_id):
    return bool(TMDB_ID_RE.fullmatch(str(tmdb_id or "")))


def play_url(tmdb_id, media_type="movie", season=1, episode=1):
    if not valid_tmdb_id(tmdb_id):
        raise ValueError("Invalid TMDB ID")
    if media_type not in {"movie", "tv"}:
        raise ValueError("Invalid media type")

    if media_type == "tv":
        try:
            season = int(season)
            episode = int(episode)
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid season or episode") from exc
        if not 1 <= season <= MAX_SEASON_NUMBER or not 1 <= episode <= MAX_EPISODE_NUMBER:
            raise ValueError("Invalid season or episode")
        return f"{MOVIE_SITE_BASE}/watch/tv/{tmdb_id}/{season}/{episode}"

    return f"{MOVIE_SITE_BASE}/watch/movie/{tmdb_id}"


def provider_embed_url(tmdb_id, season=1, episode=1):
    """Build the direct TV player URL accepted by VidLove.

    VidLove rejects sandboxed frames, so this URL is only rendered by our
    dedicated player page and never accepted from request input.
    """
    if not valid_tmdb_id(tmdb_id):
        raise ValueError("Invalid TMDB ID")
    try:
        season = int(season)
        episode = int(episode)
    except (TypeError, ValueError) as exc:
        raise ValueError("Invalid season or episode") from exc
    if not 1 <= season <= MAX_SEASON_NUMBER or not 1 <= episode <= MAX_EPISODE_NUMBER:
        raise ValueError("Invalid season or episode")
    options = urlencode({
        "primarycolor": "ff4d6d",
        "secondarycolor": "c49de8",
        # Keep VidLove in automatic source selection. Pinning a named source
        # can cap a title at 480p even when another source offers 1080p.
        "server": "auto",
        "hideserver": "true",
        "autoplay": "true",
        "autonext": "false",
        "episodelist": "false",
        "hideepisodelist": "true",
        "hidenextbutton": "true",
        "poster": "true",
        "pip": "true",
    })
    return f"{VIDLOVE_PLAYER_ORIGIN}/embed/tv/{tmdb_id}/{season}/{episode}?{options}"


def provider_movie_embed_url(tmdb_id):
    """Build a direct movie URL from the documented VidLove TMDB contract."""
    if not valid_tmdb_id(tmdb_id):
        raise ValueError("Invalid TMDB ID")
    options = urlencode({
        "primarycolor": "ff4d6d",
        "secondarycolor": "c49de8",
        # Keep VidLove in automatic source selection. Pinning a named source
        # can cap a title at 480p even when another source offers 1080p.
        "server": "auto",
        "hideserver": "true",
        "autoplay": "true",
        "autonext": "false",
        "hidenextbutton": "true",
        "poster": "true",
        "pip": "true",
    })
    return f"{VIDLOVE_PLAYER_ORIGIN}/embed/movie/{tmdb_id}?{options}"


def local_tv_player_url(tmdb_id, season=1, episode=1, *, title="", year="", poster=""):
    """Build a same-site TV player URL with optional sanitized display metadata."""
    provider_embed_url(tmdb_id, season, episode)
    path = f"/watch-tv/{tmdb_id}/{int(season)}/{int(episode)}"
    metadata = {}
    title = metadata_text(title)
    year = metadata_text(year, 12)
    poster = normalized_poster_url(poster)
    if title:
        metadata["title"] = title
    if year:
        metadata["year"] = year
    if poster:
        metadata["poster"] = poster
    return f"{path}?{urlencode(metadata)}" if metadata else path


def local_movie_player_url(tmdb_id, *, title="", year="", poster=""):
    """Build a same-site movie player URL with sanitized display metadata."""
    provider_movie_embed_url(tmdb_id)
    path = f"/watch-movie/{tmdb_id}"
    metadata = {}
    title = metadata_text(title)
    year = metadata_text(year, 12)
    poster = normalized_poster_url(poster)
    if title:
        metadata["title"] = title
    if year:
        metadata["year"] = year
    if poster:
        metadata["poster"] = poster
    return f"{path}?{urlencode(metadata)}" if metadata else path


def with_play_urls(results):
    hydrated = []
    if not isinstance(results, list):
        return hydrated
    for item in results[:MAX_SEARCH_RESULTS]:
        if not isinstance(item, dict):
            continue
        tmdb_id = item.get("id", "")
        if not valid_tmdb_id(tmdb_id):
            continue
        media_type = item.get("media_type", "tv" if item.get("is_tv") else "movie")
        if media_type not in {"movie", "tv"}:
            continue
        is_tv = media_type == "tv"
        title = metadata_text(item.get("title")) or "Unknown title"
        year = metadata_text(item.get("year"), 12)
        poster = normalized_poster_url(item.get("poster"))
        hydrated.append({
            "id": tmdb_id,
            "title": title,
            "year": year,
            "poster": poster,
            "type": "TV series" if is_tv else "Movie",
            "media_type": media_type,
            "is_tv": is_tv,
            "play_url": (
                local_tv_player_url(tmdb_id, title=title, year=year, poster=poster)
                if is_tv else local_movie_player_url(tmdb_id, title=title, year=year, poster=poster)
            ),
        })
    return hydrated


def search_cache_key(query):
    return "s_" + normalized_query(query).lower()


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
        "csp_nonce": g.csp_nonce,
        "settings": settings,
        "admin_config": admin_config(),
    }
    base.update(extra)
    return base


def bounded_response_json(response, max_bytes=MAX_CATALOG_RESPONSE_BYTES):
    """Decode JSON without allowing an upstream to stream an unbounded body."""
    if not isinstance(response, requests.Response):
        return response.json()

    declared_length = response.headers.get("Content-Length", "")
    if declared_length.isdigit() and int(declared_length) > max_bytes:
        raise ValueError("Upstream response is too large")

    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        size += len(chunk)
        if size > max_bytes:
            raise ValueError("Upstream response is too large")
        chunks.append(chunk)
    return json.loads(b"".join(chunks))


def fetch_catalog_results(query):
    primary = []
    if TMDB_API_KEY:
        res = None
        try:
            res = requests.get(
                f"{TMDB_API_BASE}/search/multi",
                params={
                    "api_key": TMDB_API_KEY,
                    "query": query,
                },
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0"},
                allow_redirects=False,
                stream=True,
            )
            res.raise_for_status()
            data = bounded_response_json(res)
            if isinstance(data, dict) and isinstance(data.get("results"), list):
                primary = [
                    item for item in data["results"]
                    if isinstance(item, dict) and item.get("media_type") in {"movie", "tv"}
                ]
                primary.sort(
                    key=lambda item: item.get("popularity", 0)
                    if isinstance(item.get("popularity", 0), (int, float))
                    and not isinstance(item.get("popularity", 0), bool)
                    else 0,
                    reverse=True,
                )
                primary = primary[:14]
                if len(primary) >= 5:
                    return primary
        except Exception as e:
            app.logger.warning("Primary catalog search failed for %r: %s", query, e)
        finally:
            if res is not None:
                res.close()

    if not SEARCH_FALLBACK_URL:
        return primary

    res = None
    try:
        res = requests.get(
            SEARCH_FALLBACK_URL,
            params={"q": query},
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
            allow_redirects=False,
            stream=True,
        )
        res.raise_for_status()
        data = bounded_response_json(res)
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return []
        combined = list(primary)
        seen = {
            (str(item.get("media_type", "")), str(item.get("id", "")))
            for item in combined
        }
        for item in data["results"]:
            if not isinstance(item, dict) or item.get("media_type") not in {"movie", "tv"}:
                continue
            identity = (str(item.get("media_type", "")), str(item.get("id", "")))
            if identity in seen:
                continue
            seen.add(identity)
            combined.append(item)
            if len(combined) >= 18:
                break
        return combined
    except Exception as e:
        app.logger.warning("Fallback catalog search failed for %r: %s", query, e)
        return primary
    finally:
        if res is not None:
            res.close()


def catalog_query_parts(query):
    """Mirror 67movies' year-token handling before catalog lookup."""
    match = re.search(r"\b(?:19|20)\d{2}\b", query)
    if not match:
        return query, ""
    text = f"{query[:match.start()]} {query[match.end():]}"
    text = re.sub(r"\s{2,}", " ", text).strip()
    return (text if len(text) >= 2 else query), match.group(0)


def fetch_tmdb_metadata(path):
    """Fetch bounded TMDB metadata, with VidLove's proxy as a no-key fallback."""
    if not isinstance(path, str) or not re.fullmatch(
        r"/3/(?:tv|movie)/[1-9]\d{0,9}(?:/season/[1-9]\d{0,2})?",
        path,
    ):
        return {}

    timestamp = now_ts()
    with metadata_cache_lock:
        cached = metadata_cache.get(path)
        if cached and cached[0] > timestamp:
            return cached[1]

    providers = []
    if TMDB_API_KEY:
        providers.append((f"https://api.themoviedb.org{path}", {
            "api_key": TMDB_API_KEY,
            "language": "en-US",
        }))
    providers.append((f"{VIDLOVE_API_ORIGIN}/tmdb{path}", {"language": "en-US"}))

    for url, params in providers:
        response = None
        try:
            response = requests.get(
                url,
                params=params,
                timeout=6,
                headers={"Accept": "application/json", "User-Agent": "GoonToThis/1.0"},
                allow_redirects=False,
                stream=True,
            )
            response.raise_for_status()
            data = bounded_response_json(response)
            if isinstance(data, dict):
                with metadata_cache_lock:
                    if len(metadata_cache) >= 500:
                        expired = [key for key, value in metadata_cache.items() if value[0] <= timestamp]
                        for key in expired:
                            metadata_cache.pop(key, None)
                        if len(metadata_cache) >= 500:
                            metadata_cache.pop(next(iter(metadata_cache)))
                    metadata_cache[path] = (timestamp + METADATA_CACHE_TTL_SECONDS, data)
                return data
        except Exception as exc:
            app.logger.warning("Metadata lookup failed for %s via %s: %s", path, url, exc)
        finally:
            if response is not None:
                response.close()
    return {}


def fetch_tv_player_metadata(tmdb_id, season):
    """Fetch real show and selected-season metadata without requiring local setup."""
    if not valid_tmdb_id(tmdb_id):
        return {}
    if not 1 <= season <= MAX_SEASON_NUMBER:
        return {}

    try:
        show = fetch_tmdb_metadata(f"/3/tv/{tmdb_id}")
        if not show:
            return {}

        season_data = fetch_tmdb_metadata(f"/3/tv/{tmdb_id}/season/{season}")

        episodes = []
        for item in season_data.get("episodes", [])[:200]:
            if not isinstance(item, dict):
                continue
            number = item.get("episode_number")
            if not isinstance(number, int) or not 1 <= number <= MAX_EPISODE_NUMBER:
                continue
            episodes.append({
                "number": number,
                "name": metadata_text(item.get("name"), 160) or f"Episode {number}",
                "air_date": metadata_text(item.get("air_date"), 16),
            })

        genres = []
        for item in show.get("genres", [])[:4]:
            if isinstance(item, dict):
                name = metadata_text(item.get("name"), 32)
                if name:
                    genres.append(name)

        season_episode_counts = {}
        for item in show.get("seasons", [])[:MAX_SEASON_NUMBER + 1]:
            if not isinstance(item, dict):
                continue
            number = item.get("season_number")
            episode_count = item.get("episode_count")
            if (
                isinstance(number, int)
                and isinstance(episode_count, int)
                and 1 <= number <= MAX_SEASON_NUMBER
                and 1 <= episode_count <= MAX_EPISODE_NUMBER
            ):
                season_episode_counts[number] = episode_count

        season_count = show.get("number_of_seasons")
        if not isinstance(season_count, int) or not 1 <= season_count <= MAX_SEASON_NUMBER:
            season_count = season

        return {
            "title": metadata_text(show.get("name")) or "TV Show",
            "year": metadata_text(show.get("first_air_date"), 16)[:4],
            "poster": poster_url_from_path(show.get("poster_path", "")),
            "overview": metadata_text(show.get("overview"), 700),
            "status": metadata_text(show.get("status"), 40),
            "genres": genres,
            "season_count": season_count,
            "season_episode_counts": season_episode_counts,
            "episodes": episodes,
        }
    except Exception as exc:
        app.logger.warning("TV metadata lookup failed for %s season %s: %s", tmdb_id, season, exc)
        return {}


def fetch_movie_player_metadata(tmdb_id):
    """Fetch real movie metadata without requiring local setup."""
    if not valid_tmdb_id(tmdb_id):
        return {}
    try:
        movie = fetch_tmdb_metadata(f"/3/movie/{tmdb_id}")
        if not movie:
            return {}
        genres = []
        for item in movie.get("genres", [])[:4]:
            if isinstance(item, dict):
                name = metadata_text(item.get("name"), 32)
                if name:
                    genres.append(name)
        return {
            "title": metadata_text(movie.get("title")) or "Movie",
            "year": metadata_text(movie.get("release_date"), 16)[:4],
            "poster": poster_url_from_path(movie.get("poster_path", "")),
            "overview": metadata_text(movie.get("overview"), 700),
            "status": metadata_text(movie.get("status"), 40),
            "genres": genres,
        }
    except Exception as exc:
        app.logger.warning("Movie metadata lookup failed for %s: %s", tmdb_id, exc)
        return {}


def search_movies(query):
    query = normalized_query(query)
    if not query:
        return []
    key = search_cache_key(query)
    cached = cached_search(key)
    if cached is not None:
        return cached

    catalog_query, requested_year = catalog_query_parts(query)
    results = []
    for item in fetch_catalog_results(catalog_query):
        if not isinstance(item, dict):
            continue
        media_type = item.get("media_type", "")
        tmdb_id = item.get("id", "")
        if media_type not in {"movie", "tv"} or not valid_tmdb_id(tmdb_id):
            continue

        is_tv = media_type == "tv"
        title = metadata_text(item.get("name", "") if is_tv else item.get("title", ""))
        release_date = metadata_text(
            item.get("first_air_date", "") if is_tv else item.get("release_date", ""),
            32,
        )
        if requested_year and release_date[:4] != requested_year:
            continue
        poster = poster_url_from_path(item.get("poster_path", ""))
        results.append({
            "id": tmdb_id,
            "title": title or "Unknown title",
            "year": release_date[:4] if release_date else "",
            "poster": poster,
            "type": "TV series" if is_tv else "Movie",
            "media_type": media_type,
            "is_tv": is_tv,
            "play_url": (
                local_tv_player_url(tmdb_id, title=title or "Unknown title", year=release_date[:4], poster=poster)
                if is_tv else local_movie_player_url(tmdb_id, title=title or "Unknown title", year=release_date[:4], poster=poster)
            ),
        })
        if len(results) >= MAX_SEARCH_RESULTS:
            break

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


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon_root():
    return send_from_directory(app.static_folder, "apple-touch-icon.png", mimetype="image/png")


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

    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    elif not isinstance(payload, dict):
        return admin_error("Settings must be a JSON object.", 400)
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
    q = normalized_query(request.args.get("q", ""))
    if not q:
        return redirect("/")

    query_path = "/search?" + urlencode({"q": q})
    page_title = f'{q} - {SITE_NAME} Movies'
    page_description = (
        f'Search "{q}" on GoonToThis and launch a movie or show fast, with a '
        "high-quality video experience built to beat ordinary movie websites."
    )

    return render_template(
        "results.html",
        **template_context(
            q=q,
            results=search_movies(q),
            page_title=page_title,
            page_description=page_description,
            canonical_url=f"{SITE_URL}{query_path}",
        ),
    )


@app.route("/play/<tmdb_id>")
def play(tmdb_id):
    if not valid_tmdb_id(tmdb_id):
        abort(404)
    media_type = "tv" if request.args.get("type") == "tv" else "movie"
    if media_type == "tv":
        return redirect(local_tv_player_url(tmdb_id))
    return redirect(local_movie_player_url(tmdb_id))


@app.route("/tv/<tmdb_id>")
def tv_detail(tmdb_id):
    if not valid_tmdb_id(tmdb_id):
        abort(404)
    return redirect(local_tv_player_url(tmdb_id))


@app.route("/watch-tv/<tmdb_id>/<int:season>/<int:episode>")
def watch_tv(tmdb_id, season, episode):
    if not valid_tmdb_id(tmdb_id):
        abort(404)
    try:
        embed_url = provider_embed_url(tmdb_id, season, episode)
        external_url = play_url(tmdb_id, "tv", season, episode)
    except ValueError:
        abort(404)

    supplied_title = metadata_text(request.args.get("title", ""))
    supplied_year = metadata_text(request.args.get("year", ""), 12)
    supplied_poster = normalized_poster_url(request.args.get("poster", ""))
    metadata = fetch_tv_player_metadata(tmdb_id, season)
    title = metadata.get("title") or supplied_title or "TV Show"
    year = metadata.get("year") or supplied_year
    poster = metadata.get("poster") or supplied_poster
    episodes = metadata.get("episodes") or []
    season_count = metadata.get("season_count", season)
    season_episode_counts = metadata.get("season_episode_counts") or {}

    # Never send a known-invalid TV coordinate to the provider. Some providers
    # fail over to unrelated media instead of returning a useful error.
    if metadata and season > season_count:
        return redirect(local_tv_player_url(
            tmdb_id, season_count, 1, title=title, year=year, poster=poster
        ))

    episode_numbers = [item["number"] for item in episodes]
    known_last_episode = season_episode_counts.get(season) or max(episode_numbers or [0])
    if metadata and known_last_episode and episode > known_last_episode:
        return redirect(local_tv_player_url(
            tmdb_id, season, known_last_episode, title=title, year=year, poster=poster
        ))
    if episodes and episode not in episode_numbers:
        closest_episode = min(episode_numbers, key=lambda number: abs(number - episode))
        return redirect(local_tv_player_url(
            tmdb_id, season, closest_episode, title=title, year=year, poster=poster
        ))

    current_last_episode = max(
        episode_numbers + [season_episode_counts.get(season, 0)]
    )

    previous_url = ""
    if episode > 1:
        previous_url = local_tv_player_url(
            tmdb_id, season, episode - 1, title=title, year=year, poster=poster
        )
    elif season > 1:
        previous_episode = season_episode_counts.get(season - 1, 1)
        previous_url = local_tv_player_url(
            tmdb_id, season - 1, previous_episode, title=title, year=year, poster=poster
        )

    next_url = ""
    if current_last_episode and episode >= current_last_episode:
        if season < season_count:
            next_url = local_tv_player_url(
                tmdb_id, season + 1, 1, title=title, year=year, poster=poster
            )
    else:
        next_url = local_tv_player_url(
            tmdb_id, season, episode + 1, title=title, year=year, poster=poster
        )

    return render_template(
        "player.html",
        **template_context(
            media_type="tv",
            tmdb_id=str(tmdb_id),
            season=season,
            episode=episode,
            title=title,
            year=year,
            poster=poster,
            overview=metadata.get("overview", ""),
            show_status=metadata.get("status", ""),
            genres=metadata.get("genres", []),
            season_count=season_count,
            episodes=episodes,
            previous_url=previous_url,
            next_url=next_url,
            embed_url=embed_url,
            external_url=external_url,
            page_title=f"{title} S{season} E{episode}",
            page_description=f"Watch {title}, season {season}, episode {episode} on {SITE_NAME}.",
            canonical_url=f"{SITE_URL}/watch-tv/{tmdb_id}/{season}/{episode}",
            og_image=poster or OG_IMAGE,
        ),
    )


@app.route("/watch-movie/<tmdb_id>")
def watch_movie(tmdb_id):
    if not valid_tmdb_id(tmdb_id):
        abort(404)
    try:
        embed_url = provider_movie_embed_url(tmdb_id)
        external_url = play_url(tmdb_id, "movie")
    except ValueError:
        abort(404)

    supplied_title = metadata_text(request.args.get("title", ""))
    supplied_year = metadata_text(request.args.get("year", ""), 12)
    supplied_poster = normalized_poster_url(request.args.get("poster", ""))
    metadata = fetch_movie_player_metadata(tmdb_id)
    title = metadata.get("title") or supplied_title or "Movie"
    year = metadata.get("year") or supplied_year
    poster = metadata.get("poster") or supplied_poster
    return render_template(
        "player.html",
        **template_context(
            media_type="movie",
            tmdb_id=str(tmdb_id),
            season=1,
            episode=1,
            title=title,
            year=year,
            poster=poster,
            overview=metadata.get("overview", ""),
            show_status=metadata.get("status", ""),
            genres=metadata.get("genres", []),
            season_count=1,
            episodes=[],
            embed_url=embed_url,
            external_url=external_url,
            page_title=title,
            page_description=f"Watch {title} on {SITE_NAME}.",
            canonical_url=f"{SITE_URL}/watch-movie/{tmdb_id}",
            og_image=poster or OG_IMAGE,
        ),
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
