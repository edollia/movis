from flask import Flask, request, render_template_string
import json
import os
import time
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

app = Flask(__name__)

CACHE_FILE = 'cache.json'
cache = {}

def save_cache():
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def scrape_search(query):
    cache_key = f"search_{query.lower()}"
    # if cache_key in cache:
    #     print("Cache hit")
    #     return cache[cache_key]

    url = f"https://www.lookmovie2.to/movies/search?q={query.replace(' ', '+')}"
    print(f"Scraping search: {url}")

    movies = []

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0")
        page.goto(url, wait_until="networkidle", timeout=60000)
        print("Search page loaded")

        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')

        for item in soup.find_all('div', class_='movie-item-style-2'):
            a_tag = item.find('a', href=True)
            if not a_tag or '/movies/view/' not in a_tag['href']:
                continue
            link = 'https://www.lookmovie2.to' + a_tag['href'] if a_tag['href'].startswith('/') else a_tag['href']

            img = item.find('img')
            poster_rel = img.get('data-src') or img.get('src') or '' if img else ''
            poster = 'https://www.lookmovie2.to' + poster_rel if poster_rel.startswith('/') else poster_rel

            title = img.get('alt', 'Unknown') if img else 'Unknown'
            if title == 'Unknown':
                h6 = item.find('h6')
                if h6 and h6.a:
                    title = h6.a.text.strip()

            year_tag = item.find('p', class_='year')
            year = year_tag.text.strip('() ') if year_tag else ''

            if title != 'Unknown':
                movies.append({
                    'title': title,
                    'year': year,
                    'poster': poster,
                    'link': link
                })
                print(f"  → {title} ({year}) | {poster[:70]}...")

        browser.close()

    print(f"Found {len(movies)} movies")

    if movies:
        cache[cache_key] = movies
        save_cache()

    return movies

def get_player_url(movie_link):
    cache_key = f"player_{movie_link}"
    # if cache_key in cache:
    #     print("Player from cache")
    #     return cache[cache_key]

    url = 'https://www.lookmovie2.to' + movie_link if not movie_link.startswith('http') else movie_link
    print(f"Getting player from: {url}")

    with sync_playwright() as p:
        browser = p.firefox.launch(headless=False)  # Visible - watch and help with X button if needed
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0")
        page = context.new_page()

        page.goto(url, wait_until="networkidle", timeout=60000)
        print("Play page loaded")

        # Click big play icon (force bypass interceptors)
        try:
            page.wait_for_selector('i.ion-play.big-play, .vjs-big-play-button, button.vjs-big-play-button', timeout=20000)
            play_icon = page.locator('i.ion-play.big-play, .vjs-big-play-button, button.vjs-big-play-button').first
            play_icon.hover()
            play_icon.click(force=True, timeout=15000)
            print("→ Force-clicked big play icon")
            time.sleep(4)
        except Exception as e:
            print(f"→ Play icon click failed: {e}")

        # Handle 7-10 sec countdown ad - wait for timer to end, then close X
        print("→ Waiting for ad countdown (7-10 sec)...")
        time.sleep(12)  # Give timer time to finish

        closed = False
        close_selectors = [
            'button.close', '.ad-close', '.x-close', '[class*="close"]', '[aria-label*="close"]',
            '.ad-timer button', '[class*="countdown"] button', 'button.skip', '.skip-button',
            'div.ad-overlay .close', '[role="button"][aria-label*="close"]'
        ]

        for attempt in range(5):  # Retry 5 times
            for sel in close_selectors:
                try:
                    if page.is_visible(sel, timeout=3000):
                        btn = page.locator(sel).first
                        btn.hover()
                        btn.click(force=True, timeout=5000)
                        print(f"→ Force-clicked ad close (attempt {attempt+1}): {sel}")
                        closed = True
                        time.sleep(5)
                        break
                except:
                    continue
            if closed:
                break
            time.sleep(2)  # Wait between retries

        if not closed:
            print("→ Ad close failed after retries - **manually click the X in the Firefox window now!**")

        # Wait for video to start after ad close
        time.sleep(10)

        # Intercept m3u8 requests
        m3u8_urls = []
        def handle_request(route, request):
            if 'm3u8' in request.url:
                m3u8_urls.append(request.url)
                print(f"→ Intercepted m3u8 request: {request.url}")
            route.continue_()

        page.route("**/*", handle_request)

        time.sleep(12)  # Let stream start

        if m3u8_urls:
            best = m3u8_urls[-1]  # Main playlist usually last
            print(f"→ Using intercepted m3u8: {best}")
            cache[cache_key] = best
            save_cache()
            browser.close()
            return best

        # Fallback scan
        html = page.content()
        m3u8s = re.findall(r'(https?://[^\s"\']+\.m3u8[^\s"\']*)', html)
        clean = [m for m in m3u8s if 'ad' not in m.lower() and len(m) > 60]
        if clean:
            best = clean[0]
            print(f"→ m3u8 found in source: {best}")
            cache[cache_key] = best
            save_cache()
            browser.close()
            return best

        print("→ No m3u8 found")
        with open('debug_play.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("   Saved debug_play.html")

        browser.close()
        return None

@app.route('/')
def home():
    html = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Matrix Movie Mirror</title>
        <style>
            body { background:black; color:#00ff00; font-family:monospace; margin:0; padding:0; overflow:hidden; height:100vh; }
            form { position:absolute; top:50%; left:50%; transform:translate(-50%,-50%); text-align:center; z-index:10; }
            input[type="text"] { background:black; color:#00ff00; border:2px solid #00ff00; font-size:28px; padding:15px; width:600px; }
            input[type="submit"] { background:black; color:#00ff00; border:2px solid #00ff00; font-size:28px; padding:15px 40px; cursor:pointer; }
        </style>
      <script data-goatcounter="https://goon2this.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</head>
    <body>
        <canvas id="matrix" style="position:absolute;top:0;left:0;width:100%;height:100%;"></canvas>
        <form action="/search" method="get">
            <input type="text" name="q" placeholder="Search movies..." autofocus>
            <br><br>
            <input type="submit" value="Search">
        </form>
        <script>
            const canvas = document.getElementById('matrix');
            const ctx = canvas.getContext('2d');
            canvas.height = window.innerHeight; canvas.width = window.innerWidth;
            const matrix = "ABCDEFGHIJKLMNOPQRSTUVWXYZ123456789@#$%^&*";
            const font = 16; const columns = canvas.width / font;
            const drops = Array(Math.floor(columns)).fill(1);
            function draw() {
                ctx.fillStyle = 'rgba(0,0,0,0.05)'; ctx.fillRect(0,0,canvas.width,canvas.height);
                ctx.fillStyle = '#00ff00'; ctx.font = font + 'px monospace';
                drops.forEach((y, i) => {
                    const text = matrix[Math.floor(Math.random() * matrix.length)];
                    ctx.fillText(text, i * font, y * font);
                    if (y * font > canvas.height && Math.random() > 0.975) drops[i] = 0;
                    drops[i]++;
                });
            }
            setInterval(draw, 35);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return "Enter a movie name", 400

    results = scrape_search(q)

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Results - {{ q }}</title>
        <style>
            body { background:black; color:#00ff00; font-family:monospace; padding:30px; margin:0; }
            h1 { text-align:center; }
            .grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(220px,1fr)); gap:25px; }
            .card { border:1px solid #00ff00; background:#001100; padding:10px; text-align:center; border-radius:6px; }
            .card img { width:100%; height:auto; border-radius:4px; }
            a { color:#00ff00; text-decoration:none; }
            a:hover { text-decoration:underline; }
        </style>
      <script data-goatcounter="https://goon2this.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</head>
    <body>
        <h1>Results for "{{ q }}"</h1>
        {% if results %}
        <div class="grid">
            {% for m in results %}
            <a href="/play?link={{ m.link }}">
                <div class="card">
                    {% if m.poster %}<img src="{{ m.poster }}" alt="{{ m.title }}">{% endif %}
                    <p>{{ m.title }} {% if m.year %}({{ m.year }}){% endif %}</p>
                </div>
            </a>
            {% endfor %}
        </div>
        {% else %}
        <p>No results found. Check terminal output.</p>
        {% endif %}
    </body>
    </html>
    """
    return render_template_string(html, q=q, results=results)

@app.route('/play')
def play():
    link = request.args.get('link', '')
    if not link:
        return "No link provided", 400

    src = get_player_url(link)

    if not src:
        return """
        <body style="background:black;color:#00ff00;font-family:monospace;padding:40px;">
            <h1>Could not auto-skip ad / find stream</h1>
            <p>In the visible Firefox window that opened:<br>
            1. Wait for the 7–10 sec ad countdown<br>
            2. When the timer ends, **manually click the X in the upper-right corner** of the ad<br>
            3. Let the movie start playing in the browser window<br>
            4. Press F12 → Network tab → filter "m3u8"<br>
            5. Copy the full .m3u8 URL that loads (long one with token/parameters)<br>
            6. Paste that URL here or reply with it — we can use it directly!</p>
        </body>
        """

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Playing</title>
        <style>body{margin:0;background:black;}</style>
      <script data-goatcounter="https://goon2this.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</head>
    <body>
        <video controls autoplay style="width:100vw;height:100vh;">
            <source src="{{ src }}" type="application/x-mpegURL">
            Your browser does not support the video tag.
        </video>
    </body>
    </html>
    """, src=src)

if __name__ == '__main__':
    app.run(debug=True)