"""
ola k ase — vidsrc.me full API implementation
"""

from flask import Flask, request, render_template_string, redirect, Response
import json, requests, os
from urllib.parse import quote

app = Flask(__name__)

VIDSRC_EMBED = "https://vidsrc.me"
VIDSRC_API   = "https://vidsrc.me"

try:    cache = json.load(open("cache.json"))
except: cache = {}

def save_cache():
    try: json.dump(cache, open("cache.json","w"))
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


def vapi(kind, type_or_path, page=1):
    key = f"vapi_{kind}_{type_or_path}_{page}"
    if key in cache: return cache[key]

    if kind == "episode":
        url = f"{VIDSRC_API}/episodes/latest/{page}"
    elif kind == "tv":
        url = f"{VIDSRC_API}/tvshows/{type_or_path}/{page}"
    else:
        url = f"{VIDSRC_API}/movies/{type_or_path}/{page}"

    print(f"[vapi] {url}")
    try:
        r    = requests.get(url, timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        data = r.json()
        raw  = data.get("result",{}).get("items", data.get("result",[]))
        if isinstance(raw, dict): raw = list(raw.values())
        out  = []
        for m in raw:
            iid   = m.get("imdb_id") or m.get("tmdb_id") or ""
            title = m.get("title") or m.get("name") or ""
            if not iid or not title: continue
            iid   = str(iid)
            rd    = m.get("release_date","") or m.get("first_air_date","") or ""
            poster= (f"https://image.tmdb.org/t/p/w300{m['poster_path']}"
                     if m.get("poster_path") else "")
            out.append({
                "id":      iid,
                "title":   title,
                "year":    rd[:4],
                "poster":  poster,
                "type":    "TV Series" if kind in ("tv","episode") else "",
                "is_tv":   kind in ("tv","episode"),
                "season":  m.get("season"),
                "episode": m.get("episode"),
            })
        cache[key]=out; save_cache()
        return out
    except Exception as e:
        print(f"[vapi] error: {e}"); return []


FONTS = '<link href="https://fonts.googleapis.com/css2?family=Share+Tech+Mono&family=VT323&display=swap" rel="stylesheet">'

MATRIX_JS = r"""
<script>
(function(){
  var c=document.getElementById('mx'); if(!c)return;
  var x=c.getContext('2d'), F=13, iv=1000/18;
  var ch='01アイウエオカキクケコサシスセソ@#$%><=-ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  var drops=[], raf=null, lt=0, on=false;
  function init(){
    on=false; if(raf){cancelAnimationFrame(raf);raf=null;}
    c.width=window.innerWidth; c.height=window.innerHeight;
    var cols=Math.floor(c.width/F);
    drops=Array.from({length:cols},function(){
      return Math.floor(Math.random()*-(c.height/F));
    });
    x.fillStyle='#000'; x.fillRect(0,0,c.width,c.height);
    on=true; lt=performance.now(); raf=requestAnimationFrame(tick);
  }
  function tick(now){
    if(!on)return; raf=requestAnimationFrame(tick);
    var e=now-lt; if(e<iv)return; lt=now-(e%iv);
    x.fillStyle='rgba(0,0,0,0.045)'; x.fillRect(0,0,c.width,c.height);
    x.font='bold '+F+'px monospace';
    for(var i=0;i<drops.length;i++){
      var r=Math.random();
      x.fillStyle = r>.97 ? '#ffffff' : r>.9 ? '#afffaf' : '#00cc00';
      x.fillText(ch[Math.floor(Math.random()*ch.length)], i*F, drops[i]*F);
      if(drops[i]*F>c.height && Math.random()>.975) drops[i]=0;
      drops[i]++;
    }
  }
  var rt;
  window.addEventListener('resize',function(){ clearTimeout(rt); rt=setTimeout(init,150); });
  init();
})();
</script>"""

SCANLINES = """<div style="position:fixed;inset:0;pointer-events:none;z-index:900;
  background:repeating-linear-gradient(to bottom,
    transparent 0,transparent 2px,rgba(0,0,0,.08) 2px,rgba(0,0,0,.08) 3px)"></div>"""

def header(q="", show_nav=False):
    nav = ""
    if show_nav:
        nav = """<nav class="hnav">
      <a href="/new/movie">new movies</a>
      <a href="/new/tv">new shows</a>
      <a href="/recent/movie">recently added</a>
      <a href="/latest-episodes">episodes</a>
    </nav>"""
    return f"""<header>
    <a class="logo" href="/">ola k ase</a>
    <form class="srow" action="/search" method="get">
      <input type="text" name="q" value="{q}" placeholder="search..." autocomplete="off" spellcheck="false">
      <button type="submit">[go]</button>
    </form>
    {nav}
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
  padding:.48rem .85rem;
  display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;
}}
.logo{{
  font-family:'VT323',monospace;font-size:1.6rem;
  color:#00ff41;text-decoration:none;letter-spacing:.05em;
  text-shadow:0 0 10px #00ff41,0 0 30px #006620;
  white-space:nowrap;flex-shrink:0;
}}
.srow{{display:flex;flex:1;min-width:110px;max-width:340px}}
.srow input{{
  flex:1;min-width:0;background:#000;color:#00ff41;
  border:1px solid #0b200b;border-right:none;
  font-family:'Share Tech Mono',monospace;font-size:.78rem;
  padding:.38em .65em;outline:none;border-radius:2px 0 0 2px;
}}
.srow input:focus{{border-color:#00ff41}}
.srow button{{
  background:transparent;color:#00ff41;cursor:pointer;
  border:1px solid #0b200b;font-family:'Share Tech Mono',monospace;
  font-size:.76rem;padding:.38em .75em;
  border-radius:0 2px 2px 0;transition:background .15s;white-space:nowrap;
}}
.srow button:hover{{background:#001800;border-color:#00ff41}}
.hnav{{display:flex;gap:.4rem;flex-wrap:wrap;margin-left:auto}}
.hnav a{{
  font-size:.65rem;color:#00882a;text-decoration:none;
  border:1px solid #0a2a0a;padding:.22em .6em;border-radius:2px;
  transition:color .15s,border-color .15s,box-shadow .3s;white-space:nowrap;
  text-shadow:0 0 6px rgba(0,180,60,.3);
}}
.hnav a:hover{{color:#00ff41;border-color:#00ff41;box-shadow:0 0 8px rgba(0,255,65,.3)}}

.ph{{
  padding:.9rem .85rem .55rem;
  font-family:'VT323',monospace;font-size:1.25rem;
  color:#00882a;letter-spacing:.08em;
  border-bottom:1px solid #071307;
}}
.ph span{{color:#00ff41}}

.grid{{
  display:grid;
  grid-template-columns:repeat(auto-fill,minmax(min(148px,42vw),1fr));
  gap:clamp(.45rem,1.3vw,.85rem);
  padding:clamp(.65rem,1.8vw,.95rem);
  padding-bottom:4rem;
}}
.card{{
  background:#020802;border:1px solid #081508;border-radius:3px;
  overflow:hidden;text-decoration:none;color:inherit;
  display:flex;flex-direction:column;
  transition:border-color .2s,transform .2s,box-shadow .2s;
  position:relative;
}}
.card:active{{transform:scale(.97)}}
@media(hover:hover){{
  .card:hover{{
    border-color:#00ff41;
    transform:translateY(-3px) scale(1.015);
    box-shadow:0 6px 22px rgba(0,255,65,.18),0 0 0 1px rgba(0,255,65,.08);
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
  color:#00aa22;font-size:.55rem;padding:.13em .38em;
  border-radius:2px;letter-spacing:.06em;text-transform:uppercase;
}}
.bdg.tv{{color:#00ccff;border-color:#003344}}
.pwg{{
  position:absolute;bottom:0;left:0;right:0;height:42%;
  background:linear-gradient(transparent,rgba(2,8,2,.95));
  pointer-events:none;
}}
.cb{{padding:.42rem .48rem;flex:1;display:flex;flex-direction:column;gap:.15rem}}
.ct{{
  font-size:clamp(.64rem,1.8vw,.77rem);color:#ddd;font-weight:bold;
  line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;
  -webkit-box-orient:vertical;overflow:hidden;
}}
.cm{{font-size:clamp(.54rem,1.4vw,.64rem);color:#1a481a;letter-spacing:.04em}}

.empty{{
  text-align:center;padding:5rem 1rem;
  font-family:'VT323',monospace;color:#0a2a0a;
}}
.empty h2{{font-size:2.2rem;color:#165a16;margin-bottom:.4rem}}
.empty p{{font-size:.82rem;font-family:'Share Tech Mono',monospace;opacity:.4}}

.pager{{
  display:flex;justify-content:center;gap:.6rem;
  padding:1rem .85rem 2.5rem;flex-wrap:wrap;
}}
.pager a{{
  font-size:.72rem;color:#00882a;text-decoration:none;
  border:1px solid #0a2a0a;padding:.3em .9em;border-radius:2px;
  transition:all .15s;
}}
.pager a:hover{{background:#001800;border-color:#00ff41;color:#00ff41}}
.pager .cur{{color:#00ff41;border-color:#00ff41;background:rgba(0,255,65,.06)}}
</style>"""


def render_grid_page(title_html, results, q="", page=1, next_url=None, prev_url=None, show_nav=False):
    items = ""
    has_results = bool(results)
    if has_results:
        for m in results:
            is_tv  = m.get("is_tv", False)
            s, ep  = m.get("season"), m.get("episode")
            if is_tv and s and ep:
                dest = f"/watch-tv/{m['id']}/{s}/{ep}?title={quote(str(m['title']))}&year={m.get('year','')}"
            elif is_tv:
                dest = f"/tv/{m['id']}?title={quote(str(m['title']))}&year={m.get('year','')}"
            else:
                dest = f"/play/{m['id']}?title={quote(str(m['title']))}&year={m.get('year','')}"

            badge   = f'<div class="bdg{" tv" if is_tv else ""}">{"TV" if is_tv else "film"}</div>'
            img_tag = (f'<img src="{m["poster"]}" alt="" loading="lazy" '
                       f'onerror="this.style.display=\'none\'">') if m.get("poster") else ""
            nop_sty = "display:none" if m.get("poster") else ""
            ep_info = (f'<div style="position:absolute;bottom:.35rem;left:.35rem;'
                       f'font-size:.58rem;color:#00aa22;background:rgba(0,0,0,.82);'
                       f'padding:.1em .35em;border-radius:2px">S{s}E{ep}</div>'
                       if s and ep else "")
            items += f"""<a class="card" href="{dest}">
  <div class="pw">{img_tag}<div class="np" style="{nop_sty}">🎬</div>
    {badge}<div class="pwg"></div>{ep_info}</div>
  <div class="cb"><div class="ct">{m["title"]}</div>
    <div class="cm">{m.get("year","")}{(" · "+m["type"]) if m.get("type") else ""}</div>
  </div></a>"""
    else:
        items = '<div class="empty"><h2>NO SIGNAL</h2><p>nothing found</p></div>'

    effective_next = next_url if has_results else None
    pager = ""
    if prev_url or effective_next:
        pager = '<div class="pager">'
        if prev_url: pager += f'<a href="{prev_url}">← prev</a>'
        pager += f'<span class="pager cur">{page}</span>'
        if effective_next: pager += f'<a href="{effective_next}">next →</a>'
        pager += "</div>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>ola k ase</title>
  {INNER_CSS}
</head>
<body>
  {SCANLINES}
  {header(q, show_nav=show_nav)}
  <div class="ph">{title_html}</div>
  <div class="grid">{items}</div>
  {pager}
</body>
</html>"""


HOME = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>ola k ase</title>
  {FONTS}
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    html,body{{width:100%;height:100%;background:#000;overflow:hidden;
               font-family:'Share Tech Mono',monospace}}
    #mx{{position:fixed;inset:0;z-index:0}}
    .wrap{{
      position:fixed;top:50%;left:50%;
      transform:translate(-50%,-50%);
      z-index:20;width:min(94vw,520px);
      display:flex;flex-direction:column;align-items:center;
    }}
    h1{{
      font-family:'VT323',monospace;
      font-size:clamp(3.2rem,16vw,6.5rem);
      color:#00ff41;letter-spacing:.06em;line-height:1;
      margin-bottom:.5em;text-align:center;
      text-shadow:0 0 7px #00ff41,0 0 22px #00ff41,0 0 60px #008822;
      animation:glow 4s ease-in-out infinite;
    }}
    @keyframes glow{{
      0%,100%{{text-shadow:0 0 7px #00ff41,0 0 22px #00ff41,0 0 60px #008822}}
      50%{{text-shadow:0 0 12px #00ff41,0 0 40px #00ff41,0 0 100px #00ff41,0 0 200px #004400}}
    }}
    .bar{{
      display:flex;width:100%;
      border:1px solid #00ff41;border-radius:2px;overflow:hidden;
      box-shadow:0 0 20px rgba(0,255,65,.25);
      transition:box-shadow .3s;
    }}
    .bar:focus-within{{box-shadow:0 0 40px rgba(0,255,65,.55),0 0 80px rgba(0,255,65,.15)}}
    input[type=text]{{
      flex:1;min-width:0;background:rgba(0,3,0,.96);color:#00ff41;
      border:none;outline:none;caret-color:#00ff41;
      font-family:'Share Tech Mono',monospace;
      font-size:clamp(.9rem,3.5vw,1.15rem);padding:.82em 1em;
    }}
    input[type=text]::placeholder{{color:#003510;opacity:1}}
    input[type=submit]{{
      background:rgba(0,255,65,.05);color:#00ff41;border:none;
      border-left:1px solid #00ff41;cursor:pointer;flex-shrink:0;
      font-family:'Share Tech Mono',monospace;font-size:clamp(.8rem,3vw,1rem);
      padding:.82em 1.3em;transition:background .2s,color .2s;letter-spacing:.04em;
    }}
    input[type=submit]:hover{{background:#00ff41;color:#000}}
    .links{{
      display:flex;gap:.5rem;flex-wrap:wrap;justify-content:center;
      margin-top:1.2em;
    }}
    @keyframes linkglow{{
      0%,100%{{color:#00992a;border-color:#005515;box-shadow:0 0 4px rgba(0,200,60,.12)}}
      50%  {{color:#00dd40;border-color:#009922;box-shadow:0 0 11px rgba(0,255,65,.38),0 0 22px rgba(0,255,65,.12)}}
    }}
    .links a{{
      font-size:.65rem;text-decoration:none;
      border:1px solid #005515;padding:.22em .65em;border-radius:2px;
      letter-spacing:.08em;
      color:#00992a;
      animation:linkglow 2.8s ease-in-out infinite;
    }}
    .links a:nth-child(1){{animation-delay:0s}}
    .links a:nth-child(2){{animation-delay:.45s}}
    .links a:nth-child(3){{animation-delay:.9s}}
    .links a:nth-child(4){{animation-delay:1.35s}}
    .links a:nth-child(5){{animation-delay:1.8s}}
    .links a:hover{{
      animation:none;
      color:#00ff41;border-color:#00ff41;
      box-shadow:0 0 16px rgba(0,255,65,.55);
    }}
  </style>
</head>
<body>
  <canvas id="mx"></canvas>
  <div style="position:fixed;inset:0;pointer-events:none;z-index:10;
    background:repeating-linear-gradient(to bottom,
      transparent 0,transparent 2px,rgba(0,0,0,.07) 2px,rgba(0,0,0,.07) 3px)"></div>
  <div class="wrap">
    <h1>ola k ase</h1>
    <form action="/search" method="get" style="width:100%">
      <div class="bar">
        <input type="text" name="q"
               placeholder="search movies &amp; tv shows..."
               autofocus autocomplete="off" spellcheck="false">
        <input type="submit" value="[enter]">
      </div>
    </form>
    <div class="links">
      <a href="/new/movie">new movies</a>
      <a href="/new/tv">new shows</a>
      <a href="/recent/movie">recently added</a>
      <a href="/recent/tv">recent tv</a>
      <a href="/latest-episodes">latest episodes</a>
    </div>
  </div>
  {MATRIX_JS}
</body>
</html>"""


TV_TMPL = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>{{{{ title }}}} — ola k ase</title>
  {INNER_CSS}
  <style>
    .tv-wrap{{max-width:600px;margin:0 auto;padding:1.2rem .85rem 3rem}}
    .tv-title{{
      font-family:'VT323',monospace;
      font-size:clamp(2rem,8vw,3rem);
      color:#00ff41;text-shadow:0 0 10px #00ff41;
      letter-spacing:.05em;line-height:1.1;margin-bottom:.2em;
    }}
    .tv-meta{{font-size:.72rem;color:#1a4a1a;margin-bottom:1.5rem;letter-spacing:.06em}}
    label{{display:block;font-size:.72rem;color:#00882a;
           letter-spacing:.1em;margin-bottom:.3em}}
    select{{
      display:block;width:100%;max-width:260px;
      background:#020802;color:#00ff41;
      border:1px solid #0a280a;border-radius:2px;
      font-family:'Share Tech Mono',monospace;font-size:.85rem;
      padding:.45em .65em;outline:none;cursor:pointer;margin-bottom:1rem;
      appearance:none;-webkit-appearance:none;
    }}
    select:focus{{border-color:#00ff41}}
    .watch-btn{{
      display:inline-block;margin-top:.5rem;
      background:rgba(0,255,65,.07);color:#00ff41;
      border:1px solid #00ff41;border-radius:3px;
      font-family:'VT323',monospace;font-size:1.5rem;
      letter-spacing:.1em;text-align:center;
      padding:.45em 1.5em;text-decoration:none;
      transition:background .2s,box-shadow .2s;
      box-shadow:0 0 14px rgba(0,255,65,.18);
    }}
    .watch-btn:hover{{background:rgba(0,255,65,.2);box-shadow:0 0 30px rgba(0,255,65,.4)}}
    .also{{margin-top:1.8rem;font-size:.7rem;color:#0a2a0a;letter-spacing:.08em}}
    .also a{{color:#00882a;text-decoration:none}}
    .also a:hover{{color:#00ff41}}
  </style>
</head>
<body>
  {SCANLINES}
  {header()}
  <div class="tv-wrap">
    <div class="tv-title">{{{{ title }}}}</div>
    <div class="tv-meta">{{{{ imdb_id }}}}{{{{ " · " + year if year else "" }}}} · tv series</div>

    <label>season</label>
    <select id="ss">
      {{% for s in range(1,51) %}}
      <option value="{{{{ s }}}}">season {{{{ s }}}}</option>
      {{% endfor %}}
    </select>

    <label>episode</label>
    <select id="se">
      {{% for e in range(1,51) %}}
      <option value="{{{{ e }}}}">episode {{{{ e }}}}</option>
      {{% endfor %}}
    </select>

    <a class="watch-btn" id="wbtn"
       href="/watch-tv/{{{{ imdb_id }}}}/1/1?title={{{{ title|urlencode }}}}&year={{{{ year }}}}">
      ▶ watch
    </a>
    <div class="also">
      or watch from start →
      <a href="/watch-tv/{{{{ imdb_id }}}}/1/1?title={{{{ title|urlencode }}}}&year={{{{ year }}}}">S1E1</a>
    </div>
  </div>
  <script>
  (function(){{
    var ss=document.getElementById('ss');
    var se=document.getElementById('se');
    var wb=document.getElementById('wbtn');
    var id='{{{{ imdb_id }}}}', t='{{{{ title|e }}}}', y='{{{{ year }}}}';
    function upd(){{
      wb.href='/watch-tv/'+id+'/'+ss.value+'/'+se.value+
              '?title='+encodeURIComponent(t)+'&year='+y;
    }}
    ss.addEventListener('change',upd);
    se.addEventListener('change',upd);
  }})();
  </script>
</body>
</html>"""


PLAYER_TMPL = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
  <title>{{{{ title }}}} — ola k ase</title>
  {FONTS}
  <style>
    *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
    html,body{{width:100%;height:100%;background:#000;overflow:hidden;
               font-family:'Share Tech Mono',monospace}}
    #tb{{
      position:fixed;top:0;left:0;right:0;height:40px;
      background:rgba(0,0,0,.8);backdrop-filter:blur(12px);
      -webkit-backdrop-filter:blur(12px);
      border-bottom:1px solid rgba(0,255,65,.1);
      display:flex;align-items:center;gap:.75rem;padding:0 .85rem;
      z-index:1000;transition:opacity .45s,transform .45s;
    }}
    #tb.h{{opacity:0;transform:translateY(-100%);pointer-events:none}}
    .tl{{
      font-family:'VT323',monospace;font-size:1.4rem;
      color:#00ff41;text-decoration:none;letter-spacing:.05em;
      text-shadow:0 0 8px #00ff41;white-space:nowrap;flex-shrink:0;
    }}
    .tt{{
      font-size:.7rem;color:#1e5a1e;flex:1;
      overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
    }}
    .bk{{
      color:#008a18;text-decoration:none;font-size:.68rem;
      border:1px solid #082008;padding:.2em .65em;border-radius:2px;
      transition:all .15s;white-space:nowrap;flex-shrink:0;
    }}
    .bk:hover{{background:#001200;border-color:#00ff41;color:#00ff41}}
    #pl{{position:fixed;inset:0;padding-top:40px}}
    iframe{{width:100%;height:100%;border:none;display:block;background:#000}}
    #sl{{position:fixed;inset:0;pointer-events:none;z-index:500;
         background:repeating-linear-gradient(to bottom,
           transparent 0,transparent 2px,rgba(0,0,0,.06) 2px,rgba(0,0,0,.06) 3px)}}
  </style>
</head>
<body>
  <div id="tb">
    <a class="tl" href="/">ola k ase</a>
    <div class="tt">
      ▶ {{{{ title }}}}
      {{%- if year %}} ({{{{ year }}}}){{%- endif %}}
      {{%- if season %}} · S{{{{ season }}}}E{{{{ episode }}}}{{%- endif %}}
    </div>
    <a class="bk" href="javascript:history.back()">← back</a>
  </div>
  <div id="pl">
    <iframe src="{{{{ embed_url }}}}"
            allowfullscreen
            allow="autoplay; fullscreen; encrypted-media; picture-in-picture; gyroscope; accelerometer"
            referrerpolicy="origin"
            scrolling="no"></iframe>
  </div>
  <div id="sl"></div>
  <script>
  (function(){{
    var tb=document.getElementById('tb'), t;
    function show(){{
      tb.classList.remove('h');
      clearTimeout(t);
      t=setTimeout(function(){{ tb.classList.add('h'); }}, 3500);
    }}
    document.addEventListener('mousemove', show, {{passive:true}});
    document.addEventListener('touchstart', show, {{passive:true}});
    document.addEventListener('click', show, {{passive:true}});
    show();
  }})();
  </script>
</body>
</html>"""


@app.route("/")
def home():
    return HOME

@app.route("/search")
def search():
    q = request.args.get("q","").strip()
    if not q: return redirect("/")
    return render_grid_page(f'results for <span>"{q}"</span>', search_imdb(q), q=q, show_nav=False)

@app.route("/new/<kind>")
@app.route("/new/<kind>/<int:page>")
def new_(kind, page=1):
    kind = "tv" if kind == "tv" else "movie"
    label = "new tv" if kind == "tv" else "new movies"
    p = max(1, page)
    return render_grid_page(f'<span>{label}</span>', vapi(kind, "new", p),
        page=p,
        prev_url=f"/new/{kind}/{p-1}" if p > 1 else None,
        next_url=f"/new/{kind}/{p+1}",
        show_nav=True)

@app.route("/recent/<kind>")
@app.route("/recent/<kind>/<int:page>")
def recent_(kind, page=1):
    kind = "tv" if kind == "tv" else "movie"
    label = "recently added tv" if kind == "tv" else "recently added movies"
    p = max(1, page)
    return render_grid_page(f'<span>{label}</span>', vapi(kind, "add", p),
        page=p,
        prev_url=f"/recent/{kind}/{p-1}" if p > 1 else None,
        next_url=f"/recent/{kind}/{p+1}",
        show_nav=True)

@app.route("/latest-episodes")
@app.route("/latest-episodes/<int:page>")
def latest_eps(page=1):
    p = max(1, page)
    return render_grid_page('<span>latest episodes</span>', vapi("episode", "latest", p),
        page=p,
        prev_url=f"/latest-episodes/{p-1}" if p > 1 else None,
        next_url=f"/latest-episodes/{p+1}",
        show_nav=True)

@app.route("/play/<imdb_id>")
def play(imdb_id):
    title = request.args.get("title", "Movie")
    year  = request.args.get("year", "")
    embed = f"{VIDSRC_EMBED}/embed/movie?imdb={imdb_id}"
    return render_template_string(PLAYER_TMPL,
        title=title, year=year, embed_url=embed,
        season=None, episode=None)

@app.route("/tv/<imdb_id>")
def tv_detail(imdb_id):
    title = request.args.get("title", "Show")
    year  = request.args.get("year", "")
    return render_template_string(TV_TMPL,
        imdb_id=imdb_id, title=title, year=year)

@app.route("/watch-tv/<imdb_id>/<int:season>/<int:episode>")
def watch_tv(imdb_id, season, episode):
    title = request.args.get("title", "Show")
    year  = request.args.get("year", "")
    embed = f"{VIDSRC_EMBED}/embed/tv?imdb={imdb_id}&season={season}&episode={episode}"
    return render_template_string(PLAYER_TMPL,
        title=title, year=year, embed_url=embed,
        season=season, episode=episode)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
