#!/usr/bin/env python3
"""Build the ackacademy.org static site.

    python3 build.py                      # src/ -> docs/
    python3 build.py --refresh-playlists  # also re-fetch the YouTube playlists

Source lives in src/:
    pages/*.html   one file per page. Lines before '---' are `key: value` front matter
                   (title, description, route, class, og_image). `index.html` is the home page.
    blog/*.html    one file per blog post (title, date, thumb front matter)
    css/, js/, assets/  copied as-is into docs/
    static/        copied into the root of docs/ unchanged (e.g. the standalone BinderClip page)

Write internal links and asset paths root-relative ("/math/", "/assets/img/logo.png").
The build rewrites them relative to each page, so the site works from any URL
(the custom domain, the github.io preview, or a local `python3 -m http.server`).

docs/ is generated; GitHub Pages serves it. Don't edit docs/ by hand.
"""
import html
import json
import os
import re
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
OUT = os.path.join(ROOT, "docs")
DOMAIN = "https://www.ackacademy.org"
GA_ID = "G-9N4STLSL52"
DEFAULT_DESC = "Math is a Skill. Build it through Practice!"
OG_DEFAULT = "/assets/img/og-image.jpg"

# Blog listing order (newest first, as on the old site) and the Math topic cards.
BLOG_ORDER = [
    "one-flashcard-at-a-time",
    "whatever-happened-to-the-almost-smartphone",
    "free-learning",
    "learn-drive-engagement-matrix",
    "active-absorption-learn-drive",
    "passive-disengagement-learn-drive",
    "productive-struggle-why-challenge-is-essential-to-learning",
    "confidence-competence-matrix",
    "smart-worksheets-spaced-repetition",
]
MATH_CARDS = [
    ("Start Here", "/blog/start-here/", "/assets/img/teacher-student.png"),
    ("Expression, Equations, Operations", "/expression-equations-operations/", "/assets/img/usk031JiHYblXH1247LVRAoDo.png"),
    ("Exponents", "/exponents/", "/assets/img/sgW5KsNLrQSO62Zjh9Qf173qHN8.webp"),
    ("Factors and Multiples", "/factors-and-multiples/", "/assets/img/wevyAA96NxJ07QWUdpM3mrOUghQ.png"),
    ("Fractions", "/fractions/", "/assets/img/S3PA6pccAc4o1uauWRsFCPr3eY.png"),
    ("Decimals", "/decimals/", "/assets/img/kw70VixhMrgakDAukU2a61L1c.png"),
]
PLAYLISTS_JSON = os.path.join(ROOT, "data", "playlists.json")
PLAYLIST_VIDEOS = 9  # how many recent videos each topic page shows


# ---------------------------------------------------------------- helpers
def read_page(path):
    """Split `key: value` front matter from the body."""
    text = open(path, encoding="utf-8").read()
    meta = {}
    if "\n---\n" in text:
        head, body = text.split("\n---\n", 1)
        for line in head.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    else:
        body = text
    return meta, body.strip()


def rel_links(page_html, route):
    """Rewrite root-relative href/src ("/x") to be relative to the page at `route`."""
    depth = route.strip("/").count("/") + 1 if route.strip("/") else 0
    prefix = "../" * depth if depth else "./"

    def fix(m):
        attr, quote, url = m.group(1), m.group(2), m.group(3)
        if url.startswith("//"):
            return m.group(0)
        return f"{attr}={quote}{prefix}{url[1:] or ''}{quote}"

    return re.sub(r'\b(href|src|data-src|poster)=(["\'])(/[^"\']*)\2', fix, page_html)


def e(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- YouTube playlists
def fetch_playlist(pid):
    """Latest videos in a playlist, from YouTube's public RSS feed (no API key)."""
    url = f"https://www.youtube.com/feeds/videos.xml?playlist_id={pid}"
    with urllib.request.urlopen(url, timeout=30) as r:
        root = ET.fromstring(r.read())
    ns = {"a": "http://www.w3.org/2005/Atom", "y": "http://www.youtube.com/xml/schemas/2015"}
    out = []
    for entry in root.findall("a:entry", ns):
        out.append({"id": entry.find("y:videoId", ns).text, "title": entry.find("a:title", ns).text})
    return out


def load_playlists():
    if os.path.exists(PLAYLISTS_JSON):
        return json.load(open(PLAYLISTS_JSON, encoding="utf-8"))
    return {}


def refresh_playlists(ids):
    data = load_playlists()
    for pid in ids:
        data[pid] = fetch_playlist(pid)
        print(f"  playlist {pid}: {len(data[pid])} videos")
    os.makedirs(os.path.dirname(PLAYLISTS_JSON), exist_ok=True)
    json.dump(data, open(PLAYLISTS_JSON, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return data


def youtube_grid(pid, playlists):
    videos = playlists.get(pid, [])[:PLAYLIST_VIDEOS]
    if not videos:
        return f'<p class="muted">Videos are on <a href="https://www.youtube.com/playlist?list={pid}">YouTube</a>.</p>'
    cards = []
    for v in videos:
        cards.append(
            f'<a class="vcard" href="https://www.youtube.com/watch?v={v["id"]}&list={pid}" target="_blank" rel="noopener">'
            f'<span class="vthumb"><img loading="lazy" src="https://i.ytimg.com/vi/{v["id"]}/hqdefault.jpg" alt=""></span>'
            f'<span class="vtitle">{e(v["title"])}</span></a>'
        )
    return '<div class="vgrid">' + "".join(cards) + "</div>"


# ---------------------------------------------------------------- layout
NAV = [("Home", "/"), ("Math", "/math/"), ("Blog", "/blog/"), ("About Us", "/about-us/")]


def layout(route, title, desc, body, body_class="", og_image=None, og_type="website", extra_head=""):
    canonical = DOMAIN + route
    og = DOMAIN + (og_image or OG_DEFAULT)
    nav = "".join(
        f'<a href="{href}"{" aria-current=\"page\"" if href == route or (href != "/" and route.startswith(href)) else ""}>{label}</a>'
        for label, href in NAV
    )
    doodles = (
        '<img class="doodles" src="/assets/img/doodles-wide.png" alt="" width="489" height="174">'
        if body_class.split()[:1] == ["home"]
        else ""
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="{og_type}">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{og}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" type="image/png" href="/assets/img/logo-small.png">
<link rel="preload" href="/assets/fonts/playfair-display.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/css/site.css">
{extra_head}
<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','{GA_ID}');</script>
</head>
<body class="{body_class}">
<header class="site-header">
  <div class="header-inner">
    <a class="logo" href="/"><img src="/assets/img/logo.png" alt="A.C.K. Academy" width="61" height="62"></a>
    <p class="site-title"><a href="/">A.C.K. Academy</a></p>
    <nav aria-label="Main">{nav}</nav>
    {doodles}
  </div>
</header>
<main>
{body}
</main>
<footer class="site-footer">
  <nav aria-label="Footer"><a href="/privacy-policy/">Privacy Policy</a><a href="/contact-us/">Contact Us</a><a href="/terms-of-service/">Terms of Service</a></nav>
  <p class="made">Made with ❤️ in N.Y.C</p>
</footer>
<script src="/js/site.js" defer></script>
</body>
</html>
"""
    return rel_links(page, route)


def write(route, content):
    path = os.path.join(OUT, route.strip("/"), "index.html") if route.strip("/") else os.path.join(OUT, "index.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "w", encoding="utf-8").write(content)


# ---------------------------------------------------------------- build
def main():
    refresh = "--refresh-playlists" in sys.argv
    pages = {}  # route -> (meta, body)
    for name in sorted(os.listdir(os.path.join(SRC, "pages"))):
        if not name.endswith(".html"):
            continue
        meta, body = read_page(os.path.join(SRC, "pages", name))
        route = meta.get("route") or ("/" if name == "index.html" else "/" + name[:-5] + "/")
        pages[route] = (meta, body)

    posts = {}
    for name in sorted(os.listdir(os.path.join(SRC, "blog"))):
        if name.endswith(".html"):
            meta, body = read_page(os.path.join(SRC, "blog", name))
            posts[name[:-5]] = (meta, body)

    # YouTube playlists referenced as {{youtube_grid:ID}}
    wanted = sorted({m for _, b in pages.values() for m in re.findall(r"\{\{youtube_grid:([A-Za-z0-9_-]+)\}\}", b)})
    playlists = refresh_playlists(wanted) if refresh else load_playlists()
    missing = [p for p in wanted if p not in playlists]
    if missing:
        print("note: no cached videos for", ", ".join(missing), "- run with --refresh-playlists")

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    for d in ("assets", "css", "js"):
        if os.path.isdir(os.path.join(SRC, d)):
            shutil.copytree(os.path.join(SRC, d), os.path.join(OUT, d))
    # src/static/ is copied verbatim into the site root (e.g. static/binderclip/index.html -> /binderclip/)
    static = os.path.join(SRC, "static")
    if os.path.isdir(static):
        shutil.copytree(static, OUT, dirs_exist_ok=True)

    # blog cards / math cards
    def card(title, href, thumb, date=""):
        return (
            f'<a class="card" href="{href}"><span class="card-text"><span class="card-title">{e(title)}</span>'
            + (f'<span class="card-date">{e(date)}</span>' if date else "")
            + f'</span><img loading="lazy" src="{thumb}" alt="" width="198" height="108"></a>'
        )

    blog_cards = "".join(
        card(posts[s][0]["title"], f"/blog/{s}/", posts[s][0].get("thumb", OG_DEFAULT), posts[s][0].get("date", ""))
        for s in BLOG_ORDER
    )
    math_cards = "".join(card(t, h, i) for t, h, i in MATH_CARDS)

    routes = []
    for route, (meta, body) in pages.items():
        body = body.replace("{{blog_cards}}", blog_cards).replace("{{math_cards}}", math_cards)
        body = re.sub(r"\{\{youtube_grid:([A-Za-z0-9_-]+)\}\}", lambda m: youtube_grid(m.group(1), playlists), body)
        write(
            route,
            layout(
                route,
                meta.get("title", "A.C.K. Academy"),
                meta.get("description", DEFAULT_DESC),
                body,
                meta.get("class", ""),
                meta.get("og_image"),
            ),
        )
        routes.append(route)

    for slug, (meta, body) in posts.items():
        route = f"/blog/{slug}/"
        date = meta.get("date", "")
        article = (
            f'<article class="doc post"><h1>{e(meta["title"])}</h1>'
            + (f'<p class="post-date">{e(date)}</p>' if date else "")
            + f'<div class="doc-body">{body}</div>'
            + '<p class="back"><a href="/blog/">← All posts</a></p></article>'
        )
        write(
            route,
            layout(route, meta["title"], date or meta["title"], article, "doc-page", meta.get("thumb"), "article"),
        )
        routes.append(route)
        # old Framer URL /blog-detail/<slug> -> forward to the new one
        stub = (
            f'<!doctype html><meta charset="utf-8"><title>Redirecting…</title>'
            f'<link rel="canonical" href="{DOMAIN}{route}"><meta http-equiv="refresh" content="0; url={route}">'
            f'<p>Moved to <a href="{route}">{route}</a>.</p>'
        )
        write(f"/blog-detail/{slug}/", rel_links(stub, f"/blog-detail/{slug}/"))

    # standalone pages copied from src/static/ (e.g. /binderclip/)
    for dirpath, _, files in os.walk(os.path.join(SRC, "static")):
        if "index.html" in files:
            routes.append("/" + os.path.relpath(dirpath, os.path.join(SRC, "static")).strip("./") + "/")

    # 404
    nf = layout("/404.html", "Page not found · A.C.K. Academy", DEFAULT_DESC,
                '<article class="doc"><h1>Page not found</h1><p>That page has moved or never existed. '
                'Try the <a href="/">home page</a>, the <a href="/math/">Math</a> section or the <a href="/blog/">blog</a>.</p></article>',
                "doc-page")
    # 404.html is served from any depth, so use absolute URLs for it
    nf = nf.replace('"./', '"/').replace('"../', '"/')
    open(os.path.join(OUT, "404.html"), "w", encoding="utf-8").write(nf)

    # sitemap, robots, CNAME, .nojekyll
    urls = "".join(f"<url><loc>{DOMAIN}{r}</loc></url>\n" for r in sorted(routes))
    open(os.path.join(OUT, "sitemap.xml"), "w").write(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "</urlset>\n"
    )
    open(os.path.join(OUT, "robots.txt"), "w").write(f"User-agent: *\nAllow: /\n\nSitemap: {DOMAIN}/sitemap.xml\n")
    open(os.path.join(OUT, "CNAME"), "w").write("www.ackacademy.org\n")
    open(os.path.join(OUT, ".nojekyll"), "w").write("")
    print(f"built {len(routes)} pages -> docs/")


if __name__ == "__main__":
    main()
