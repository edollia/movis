"""
GoonToThis - PlayIMDb link implementation.
"""

import json
import os
import re
from urllib.parse import quote

import requests
from flask import Flask, abort, redirect, render_template, request, send_from_directory

app = Flask(__name__)

PLAY_IMDB_TITLE_BASE = "https://playimdb.com/title"
CACHE_PATH = os.environ.get("CACHE_PATH", "/tmp/movis-cache.json")
IMDB_ID_RE = re.compile(r"^tt\d+$")

SITE_NAME = "GoonToThis"
SITE_URL = "https://goontothis.com"
SITE_DESCRIPTION = "Search a movie or show, then tap a card to go right to it."

GOATCOUNTER_SRC = "//gc.zgo.at/count.js"
GOATCOUNTER_SITE = "https://goon2this.goatcounter.com/count"


def load_cache():
    try:
        with open(CACHE_PATH) as fh:
            return json.load(fh)
    except Exception:
        return {}


cache = load_cache()


def save_cache():
    directory = os.path.dirname(CACHE_PATH)
    tmp_path = f"{CACHE_PATH}.tmp"

    try:
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(tmp_path, "w") as fh:
            json.dump(cache, fh)
        os.replace(tmp_path, CACHE_PATH)
    except Exception:
        pass


def valid_imdb_id(imdb_id):
    return bool(IMDB_ID_RE.fullmatch(imdb_id or ""))


def play_url(imdb_id):
    return f"{PLAY_IMDB_TITLE_BASE}/{imdb_id}/"


def with_play_urls(results):
    for item in results:
        item["play_url"] = play_url(item["id"])
    return results


def template_context(**extra):
    base = {
        "site_name": SITE_NAME,
        "site_url": SITE_URL,
        "site_description": SITE_DESCRIPTION,
        "goatcounter_src": GOATCOUNTER_SRC,
        "goatcounter_site": GOATCOUNTER_SITE,
    }
    base.update(extra)
    return base


def search_imdb(query):
    key = "s_" + query.lower().strip()
    if key in cache:
        return with_play_urls(cache[key])

    q = quote(query.strip().lower())
    ch = q[0] if q else "a"

    try:
        res = requests.get(
            f"https://v2.sg.media-imdb.com/suggestion/{ch}/{q}.json",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        print(f"[search] {e}")
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

    if results:
        cache[key] = with_play_urls(results)
        save_cache()

    return results


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


@app.route("/search")
def search():
    q = request.args.get("q", "").strip()
    if not q:
        return redirect("/")

    return render_template(
        "results.html",
        **template_context(q=q, results=search_imdb(q)),
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
