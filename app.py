"""
ola k ase — PlayIMDb link implementation
"""

from flask import Flask, request, redirect
from markupsafe import escape
import json, requests, os
from urllib.parse import quote

app = Flask(__name__)

PLAY_IMDB_TITLE_BASE = "https://playimdb.com/title"
CACHE_PATH = os.environ.get("CACHE_PATH", "/tmp/movis-cache.json")


def imdb_play_url(imdb_id):
    return f"{PLAY_IMDB_TITLE_BASE}/{imdb_id}/"

try:    cache = json.load(open(CACHE_PATH))
except: cache = {}

def save_cache():
    try: json.dump(cache, open(CACHE_PATH,"w"))
    except: pass


def search_imdb(query):
    key = "s_" + query.lower().strip()
    if key in cache: return cache[key]
    q  = quote(query.strip().lower())
    ch = q[0] if q else "a"
    try:
        r = requests.get(
            f"https://v2.sg.media-imdb.com/suggestion/{ch}/{q}.json",
            timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        data = r.json()
    except Exception as e:
        print(f"[search] {e}"); return []
    out = []
    for item in data.get("d",[]):
        iid = item.get("id","")
        if not iid.startswith("tt"): continue
        img = item.get("i",{})
        qt  = item.get("q","")
        out.append({
            "id":     iid,
            "title":  item.get("l",""),
            "year":   str(item.get("y","")),
            "poster": img.get("imageUrl","") if isinstance(img,dict) else "",
            "type":   qt,
            "is_tv":  "series" in qt.lower() or "mini" in qt.lower(),
        })
    if out: cache[key]=out; save_cache()
    return out


GOAT = '<script data-goatcounter="https://goon2this.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>'

FONTS = '<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap" rel="stylesheet">'

MATRIX_JS = r"""
<script>
(function(){
  var c=document.getElementById('mx'); if(!c)return;
  var x=c.getContext('2d');
  var F=14;
  var CHARS='01アイウエオカキクケコ@#$%ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  var MSG='Just Keep Gooning';
  var drops=[], msgCols={}, cols=0;

  function init(){
    c.width=window.innerWidth; c.height=window.innerHeight;
    cols=Math.floor(c.width/F);
    drops=Array.from({length:cols},function(){
      return Math.floor(Math.random()*-(c.height/F));
    });
    msgCols={};
    x.fillStyle='#000'; x.fillRect(0,0,c.width,c.height);
  }

  function injectMsg(){
    var attempts=0, col;
    do { col=Math.floor(Math.random()*cols); attempts++; }
    while(msgCols[col]!==undefined && attempts<20);
    if(msgCols[col]===undefined) msgCols[col]=0;
    setTimeout(injectMsg, 1500+Math.random()*2500);
  }

  function tick(){
    x.fillStyle='rgba(0,0,0,0.05)'; x.fillRect(0,0,c.width,c.height);
    x.font='bold '+F+'px monospace';
    for(var i=0;i<drops.length;i++){
      var r=Math.random();
      if(msgCols[i]!==undefined){
        var ci=msgCols[i];
        if(ci<MSG.length){
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(MSG[ci], i*F, drops[i]*F);
          msgCols[i]++;
        } else {
          delete msgCols[i];
          x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
          x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], i*F, drops[i]*F);
        }
      } else {
        x.fillStyle = r>.97 ? '#fff' : r>.9 ? '#afffaf' : '#00cc00';
        x.fillText(CHARS[Math.floor(Math.random()*CHARS.length)], i*F, drops[i]*F);
      }
      if(drops[i]*F>c.height && Math.random()>.975) drops[i]=0;
      drops[i]++;
    }
  }

  var rt;
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(init,200); });
  init();
  injectMsg();
  setInterval(tick,60);
})();
</script>"""

SCANLINES = """<div style="position:fixed;inset:0;pointer-events:none;z-index:900;
  background:repeating-linear-gradient(to bottom,
    transparent 0,transparent 2px,rgba(0,0,0,.08) 2px,rgba(0,0,0,.08) 3px)"></div>"""

def header(q=""):
    q = escape(q)
    return f"""<header>
    <form class="srow" action="/search" method="get">
      <input type="text" name="q" value="{q}" placeholder="search..." autocomplete="off" spellcheck="false">
      <button type="submit">[go]</button>
    </form>
  </header>"""

INNER_CSS = f"""
{FONTS}
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{background:#010501;color:#999;font-family:'Share Tech Mono',monospace;min-height:100%}}
body{{min-height:100vh}}

header{{
  position:sticky;top:0;z-index:500;
  background:rgba(1,5,1,.97);
  border-bottom:1px solid #071307;
  backdrop-filter:blur(14px);
  -webkit-backdrop-filter:blur(14px);
  padding:.5rem .75rem;
  display:flex;align-items:center;
}}
.srow{{display:flex;flex:1;min-width:0}}
.srow input{{
  flex:1;min-width:0;background:#000;color:#00ff41;
  border:1px solid #0b200b;border-right:none;
  font-family:'Share Tech Mono',monospace;font-size:.8rem;
  padding:.4em .6em;outline:none;border-radius:2px 0 0 2px;
}}
.srow input:focus{{border-color:#00ff41}}
.srow button{{
  background:transparent;color:#00ff41;cursor:pointer;
  border:1px solid #0b200b;font-family:'Share Tech Mono',monospace;
  font-size:.76rem;padding:.4em .7em;
  border-radius:0 2px 2px 0;transition:background .15s;white-space:nowrap;flex-shrink:0;
}}
.srow button:hover{{background:#001800;border-color:#00ff41}}

.ph{{
  padding:.75rem .75rem .5rem;
  font-family:'VT323',monospace;font-size:1.2rem;
  color:#00882a;letter-spacing:.08em;
  border-bottom:1px solid #071307;
}}
.ph span{{color:#00ff41}}

.grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(min(140px,44vw),1fr));
  gap:clamp(.4rem,1.2vw,.75rem);
  padding:clamp(.6rem,1.5vw,.85rem);
  padding-bottom:3rem;
}}
.card{{
  background:#020802;border:1px solid #081508;border-radius:3px;
  overflow:hidden;text-decoration:none;color:inherit;
  display:flex;flex-direction:column;
  transition:border-color .2s,transform .2s,box-shadow .2s;
}}
.card:active{{transform:scale(.97)}}
@media(hover:hover){{
  .card:hover{{
    border-color:#00ff41;
    transform:translateY(-3px) scale(1.015);
    box-shadow:0 6px 22px rgba(0,255,65,.18);
  }}
}}
.pw{{width:100%;aspect-ratio:2/3;background:#020802;position:relative;overflow:hidden}}
.pw img{{width:100%;height:100%;object-fit:cover;display:block;transition:transform .35s}}
@media(hover:hover){{.card:hover .pw img{{transform:scale(1.07)}}}}
.np{{position:absolute;inset:0;display:flex;align-items:center;
     justify-content:center;font-size:2rem;color:#081808}}
.bdg{{
  position:absolute;top:.28rem;left:.28rem;
  background:rgba(0,0,0,.88);border:1px solid #0a2a0a;
  color:#00aa22;font-size:.52rem;padding:.12em .35em;
  border-radius:2px;letter-spacing:.06em;text-transform:uppercase;
}}
.bdg.tv{{color:#00ccff;border-color:#003344}}
.pwg{{
  position:absolute;bottom:0;left:0;right:0;height:42%;
  background:linear-gradient(transparent,rgba(2,8,2,.95));
  pointer-events:none;
}}
.cb{{padding:.38rem .42rem;flex:1;display:flex;flex-direction:column;gap:.12rem}}
.ct{{
  font-size:clamp(.62rem,1.7vw,.74rem);color:#ddd;font-weight:bold;
  line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
}}
.cm{{font-size:clamp(.52rem,1.3vw,.62rem);color:#1a481a;letter-spacing:.04em}}

.empty{{
  text-align:center;padding:5rem 1rem;
  font-family:'VT323',monospace;color:#0a2a0a;
}}
.empty h2{{font-size:2.2rem;color:#165a16;margin-bottom:.4rem}}
.empty p{{font-size:.82rem;font-family:'Share Tech Mono',monospace;opacity:.4}}
</style>"""


def render_grid_page(title_html, results, q=""):
    items = ""
    has_results = bool(results)
    if has_results:
        for m in results:
            is_tv  = m.get("is_tv", False)
            s, ep  = m.get("season"), m.get("episode")
            dest = imdb_play_url(m["id"])
            title = escape(m["title"])
            meta_type = escape(m.get("type", ""))

            badge   = f'<div class="bdg{" tv" if is_tv else ""}">{"TV" if is_tv else "film"}</div>'
            img_tag = (f'<img src="{m["poster"]}" alt="" loading="lazy" '
                       f'onerror="this.style.display=\'none\'">') if m.get("poster") else ""
            nop_sty = "display:none" if m.get("poster") else ""
            ep_info = (f'<div style="position:absolute;bottom:.35rem;left:.35rem;'
                       f'font-size:.56rem;color:#00aa22;background:rgba(0,0,0,.82);'
                       f'padding:.1em .3em;border-radius:2px">S{s}E{ep}</div>'
                       if s and ep else "")
            items += f"""<a class="card" href="{dest}">
  <div class="pw">{img_tag}<div class="np" style="{nop_sty}">🎬</div>
    {badge}<div class="pwg"></div>{ep_info}</div>
  <div class="cb"><div class="ct">{title}</div>
    <div class="cm">{escape(m.get("year",""))}{(" · "+meta_type) if meta_type else ""}</div>
  </div></a>"""
    else:
        items = '<div class="empty"><h2>NO SIGNAL</h2><p>nothing found</p></div>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>ola k ase</title>
  {INNER_CSS}
  {GOAT}
</head>
<body>
  {SCANLINES}
  {header(q)}
  <div class="ph">{title_html}</div>
  <div class="grid">{items}</div>
</body>
</html>"""


HOME = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
  <title>ola k ase</title>
  {FONTS}
  {GOAT}
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    html,body{{width:100%;height:100%;background:#000;overflow:hidden;
               font-family:'Share Tech Mono',monospace}}
    #mx{{position:fixed;inset:0;z-index:0}}
    .wrap{{
      position:fixed;top:50%;left:50%;
      transform:translate(-50%,-50%);
      z-index:20;
      width:min(92vw,480px);
      display:flex;flex-direction:column;align-items:center;
      padding:0 1rem;
    }}
    @keyframes glow{{
      0%,100%{{text-shadow:0 0 7px #00ff41,0 0 22px #00ff41,0 0 60px #008822}}
      50%{{text-shadow:0 0 14px #00ff41,0 0 45px #00ff41,0 0 110px #00ff41}}
    }}
    .bar{{
      display:flex;width:100%;
      border:1px solid #00ff41;border-radius:2px;overflow:hidden;
      box-shadow:0 0 20px rgba(0,255,65,.25);
      transition:box-shadow .3s;
    }}
    .bar:focus-within{{box-shadow:0 0 40px rgba(0,255,65,.55)}}
    input[type=text]{{
      flex:1;min-width:0;background:rgba(0,3,0,.96);color:#00ff41;
      border:none;outline:none;caret-color:#00ff41;
      font-family:'Share Tech Mono',monospace;
      font-size:clamp(.95rem,4vw,1.15rem);
      padding:.75em .9em;
    }}
    input[type=text]::placeholder{{color:#003510;opacity:1}}
    input[type=submit]{{
      background:rgba(0,255,65,.05);color:#00ff41;border:none;
      border-left:1px solid #00ff41;cursor:pointer;flex-shrink:0;
      font-family:'Share Tech Mono',monospace;
      font-size:clamp(.8rem,3.5vw,1rem);
      padding:.75em 1.1em;
      transition:background .2s;letter-spacing:.03em;
    }}
    input[type=submit]:hover{{background:#00ff41;color:#000}}
    .scan{{
      position:fixed;inset:0;pointer-events:none;z-index:10;
      background:repeating-linear-gradient(to bottom,
        transparent 0,transparent 2px,rgba(0,0,0,.07) 2px,rgba(0,0,0,.07) 3px)
    }}
  </style>
</head>
<body>
  <canvas id="mx"></canvas>
  <div class="scan"></div>
  <div class="wrap">
    <form action="/search" method="get" style="width:100%">
      <div class="bar">
        <input type="text" name="q"
               placeholder="search movies &amp; tv..."
               autofocus autocomplete="off" spellcheck="false">
        <input type="submit" value="go">
      </div>
    </form>
  </div>
  {MATRIX_JS}
</body>
</html>"""


@app.route("/")
def home():
    return HOME

@app.route("/search")
def search():
    q = request.args.get("q","").strip()
    if not q: return redirect("/")
    return render_grid_page(f'results for <span>"{escape(q)}"</span>', search_imdb(q), q=q)

@app.route("/play/<imdb_id>")
def play(imdb_id):
    return redirect(imdb_play_url(imdb_id))

@app.route("/tv/<imdb_id>")
def tv_detail(imdb_id):
    return redirect(imdb_play_url(imdb_id))

@app.route("/watch-tv/<imdb_id>/<int:season>/<int:episode>")
def watch_tv(imdb_id, season, episode):
    return redirect(imdb_play_url(imdb_id))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
