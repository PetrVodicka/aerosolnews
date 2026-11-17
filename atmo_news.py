#!/usr/bin/env python3
"""
atmo_news.py – vyhledávání populárně-vědeckých článků o atmosféře,
aerosolech, kvalitě ovzduší, klimatu a životním prostředí.

Projde RSS/Atom kanály vybraných webů, ohodnotí články podle klíčových slov
a vytvoří přehledný HTML report (+ CSV).

Instalace (jednou):
    pip install feedparser

Použití:
    python atmo_news.py                 # posledních 7 dní, otevře report v prohlížeči
    python atmo_news.py --days 30       # posledních 30 dní
    python atmo_news.py --min-score 5   # přísnější filtr
    python atmo_news.py --only-new      # jen články, které minule ještě nebyly
    python atmo_news.py --no-open       # neotvírat prohlížeč
    python atmo_news.py --narrow        # užší výběr: jen jádro tématu, posledních 30 dní
    python atmo_news.py --no-crossref   # jen RSS, bez dotazů do Crossrefu (rychlejší)
    python atmo_news.py --typ primarni  # jen primární zdroje (časopisy); popularizacni = jen weby
    python atmo_news.py --no-split      # v reportu nedělit na primární / popularizační

Seznam webů (FEEDS), klíčová slova (KEYWORDS) a časopisy pro Crossref (CROSSREF_JOURNALS)
najdete níže, upravte dle libosti. Nalezené články se ukládají do archiv_clanku.json,
takže nezmizí ani poté, co vypadnou z RSS kanálu.
"""

import argparse
import csv
import html
import json
import os
import re
import sys
import time
import urllib.request
import webbrowser
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:
    import feedparser
except ImportError:
    sys.exit("Chybí knihovna feedparser. Nainstalujte ji příkazem:  pip install feedparser")

# ---------------------------------------------------------------------------
# 1) ZDROJE: (název, URL kanálu, domovská stránka pro automatické dohledání)
#    Pokud URL kanálu nefunguje, skript zkusí najít RSS na domovské stránce.
# ---------------------------------------------------------------------------
FEEDS = [
    # --- anglické, obecná věda ---
    # ScienceAlert: hlavní kanál drží jen 10 nejnovějších článků (~1 den), rubriky ~2–3 týdny
    ("ScienceAlert", "https://www.sciencealert.com/feed", "https://www.sciencealert.com/"),
    ("ScienceAlert", "https://www.sciencealert.com/environment/feed", None),
    ("ScienceAlert", "https://www.sciencealert.com/space/feed", None),
    ("Phys.org – Environment", "https://phys.org/rss-feed/earth-news/environment/", "https://phys.org/"),
    ("Phys.org – Earth sciences", "https://phys.org/rss-feed/earth-news/earth-sciences/", "https://phys.org/"),
    ("ScienceDaily – Air quality", "https://www.sciencedaily.com/rss/earth_climate/air_quality.xml", "https://www.sciencedaily.com/"),
    ("ScienceDaily – Pollution", "https://www.sciencedaily.com/rss/earth_climate/pollution.xml", "https://www.sciencedaily.com/"),
    ("ScienceDaily – Climate", "https://www.sciencedaily.com/rss/earth_climate/climate.xml", "https://www.sciencedaily.com/"),
    ("ScienceDaily – Environmental science", "https://www.sciencedaily.com/rss/earth_climate/environmental_science.xml", "https://www.sciencedaily.com/"),
    ("Live Science", "https://www.livescience.com/feeds/all", "https://www.livescience.com/"),
    ("New Scientist – Environment", "https://www.newscientist.com/subject/environment/feed/", "https://www.newscientist.com/"),
    ("New Scientist – Earth", "https://www.newscientist.com/subject/earth/feed/", "https://www.newscientist.com/"),
    ("Quanta Magazine", "https://www.quantamagazine.org/feed/", "https://www.quantamagazine.org/"),
    ("Science News", "https://www.sciencenews.org/feed", "https://www.sciencenews.org/"),
    ("Scientific American", "https://www.scientificamerican.com/platform/syndication/rss/", "https://www.scientificamerican.com/"),
    ("Ars Technica – Science", "https://feeds.arstechnica.com/arstechnica/science", "https://arstechnica.com/science/"),
    ("The Conversation – Environment", "https://theconversation.com/global/environment/articles.atom", "https://theconversation.com/global/environment"),
    ("Nautilus", "https://nautil.us/feed/", "https://nautil.us/"),
    ("Big Think", "https://bigthink.com/feed/", "https://bigthink.com/"),
    ("IFLScience", "https://www.iflscience.com/rss", "https://www.iflscience.com/"),
    ("Popular Science", "https://www.popsci.com/feed/", "https://www.popsci.com/"),
    ("Knowable Magazine", "https://knowablemagazine.org/rss", "https://knowablemagazine.org/"),
    ("EurekAlert! – Earth science", "https://www.eurekalert.org/rss/earth_science.xml", "https://www.eurekalert.org/"),
    ("EurekAlert! – Environment", "https://www.eurekalert.org/rss/environment.xml", "https://www.eurekalert.org/"),
    # --- chemie / klima / životní prostředí ---
    ("Chemistry World", "https://www.chemistryworld.com/rss", "https://www.chemistryworld.com/"),
    ("C&EN", "https://cen.acs.org/feeds/rss/latestnews.xml", "https://cen.acs.org/"),
    ("Carbon Brief", "https://www.carbonbrief.org/feed/", "https://www.carbonbrief.org/"),
    ("Inside Climate News", "https://insideclimatenews.org/feed/", "https://insideclimatenews.org/"),
    ("NASA Earth Observatory", "https://earthobservatory.nasa.gov/feeds/earth-observatory.rss", "https://earthobservatory.nasa.gov/"),
    # --- primární vědecké časopisy ---
    ("Nature", "https://www.nature.com/nature.rss", "https://www.nature.com/nature/"),
    ("Nature Geoscience", "https://www.nature.com/ngeo.rss", "https://www.nature.com/ngeo/"),
    ("Nature Climate Change", "https://www.nature.com/nclimate.rss", "https://www.nature.com/nclimate/"),
    ("Nature Communications", "https://www.nature.com/ncomms.rss", "https://www.nature.com/ncomms/"),
    ("npj Climate and Atmospheric Science", "https://www.nature.com/npjclimatsci.rss", "https://www.nature.com/npjclimatsci/"),
    ("Science", "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=science", "https://www.science.org/journal/science"),
    ("Science Advances", "https://www.science.org/action/showFeed?type=etoc&feed=rss&jc=sciadv", "https://www.science.org/journal/sciadv"),
    ("PNAS", "https://www.pnas.org/action/showFeed?type=etoc&feed=rss&jc=pnas", "https://www.pnas.org/"),
    # --- oborové časopisy (aerosoly, atmosféra) ---
    ("Atmospheric Chemistry and Physics", "https://acp.copernicus.org/xml/rss2_0.xml", "https://acp.copernicus.org/"),
    ("Aerosol Research", "https://ar.copernicus.org/xml/rss2_0.xml", "https://ar.copernicus.org/"),
    ("Environmental Science & Technology", "https://pubs.acs.org/action/showFeed?type=axatoc&feed=rss&jc=esthag", "https://pubs.acs.org/journal/esthag"),
    ("Journal of Aerosol Science", "https://rss.sciencedirect.com/publication/science/00218502", "https://www.sciencedirect.com/journal/journal-of-aerosol-science"),
    ("Atmospheric Environment", "https://rss.sciencedirect.com/publication/science/13522310", "https://www.sciencedirect.com/journal/atmospheric-environment"),
    # --- atmosféry jiných planet a exoplanet ---
    ("Nature Astronomy", "https://www.nature.com/natastron.rss", "https://www.nature.com/natastron/"),
    ("Icarus", "https://rss.sciencedirect.com/publication/science/00191035", "https://www.sciencedirect.com/journal/icarus"),
    ("JGR: Planets", "https://agupubs.onlinelibrary.wiley.com/feed/21699100/most-recent", "https://agupubs.onlinelibrary.wiley.com/journal/21699100"),
    ("The Planetary Science Journal", "https://iopscience.iop.org/journal/rss/2632-3338", "https://iopscience.iop.org/journal/2632-3338"),
    ("AAS Nova", "https://aasnova.org/feed/", "https://aasnova.org/"),
    ("Phys.org – Planetary sciences", "https://phys.org/rss-feed/space-news/planetary-sciences/", "https://phys.org/"),
    ("Phys.org – Astronomy", "https://phys.org/rss-feed/space-news/astronomy/", "https://phys.org/"),
    ("Space.com", "https://www.space.com/feeds/all", "https://www.space.com/"),
    ("Universe Today", "https://www.universetoday.com/feed/", "https://www.universetoday.com/"),
    ("Planetary Society", "https://www.planetary.org/rss/articles", "https://www.planetary.org/"),
]

# ---------------------------------------------------------------------------
# 2) KLÍČOVÁ SLOVA: (regulární výraz, váha). Shoda v titulku se počítá 2×.
#    Výrazy jsou bez ohledu na velikost písmen; \b = hranice slova.
# ---------------------------------------------------------------------------
KEYWORDS = [
    # Jádro: aerosoly a kvalita ovzduší (váha 4)
    (r"\baerosol", 4),
    (r"\bparticulate", 4),
    (r"\bPM ?(2[.,]5|10|1)\b", 4),
    (r"\bultrafine particle", 4),
    (r"\bnanoparticle", 3),
    (r"\bair (quality|pollution|pollutant)", 4),
    (r"\bsmog\b", 4),
    (r"\bsoot\b", 4),
    (r"\bblack carbon", 4),
    (r"\bbrown carbon", 4),
    (r"\bwildfire smoke|\bsmoke plume", 4),
    (r"\bcloud condensation|\bice nucleat|\bnucleation\b", 4),
    (r"\bsecondary organic", 4),
    # Prach (obecně +3, konkrétní druh/jev +2 navíc)
    (r"\bdust(s|y|ier|iest)?\b", 3),
    (r"\b(mineral|desert|saharan|asian|airborne|atmospheric|road|soil|volcanic|cosmic|interplanetary|"
     r"interstellar|lunar|martian|meteoric|circumstellar|debris) dust\b", 2),
    (r"\bdust (storms?|devils?|lifting|deposition|emissions?|plumes?|aerosols?|particles?|grains?|events?|outbreaks?|transport|loading|layers?|clouds?)\b", 2),
    (r"\bhaboob|\bdust bowl|\bsandstorm", 3),
    (r"\bvolatile organic|\bVOCs?\b", 3),
    # Atmosféra (váha 3)
    (r"\batmospher", 3),
    (r"\btropospher|\bstratospher|\bmesospher", 3),
    (r"\bozone\b", 3),
    (r"\bnitrogen (di)?oxide|\bNO2\b|\bNOx\b", 3),
    (r"\bsulfur dioxide|\bsulphur dioxide|\bSO2\b", 3),
    (r"\bemission", 3),
    # Klima (váha 2)
    (r"\bclimate", 2),
    (r"\bgreenhouse gas", 2),
    (r"\bglobal warming", 2),
    (r"\bcarbon dioxide|\bCO2\b", 2),
    (r"\bmethane\b", 2),
    (r"\bgeoengineering|\bsolar radiation management", 3),
    (r"\bradiative forcing", 3),
    # Životní prostředí (váha 2)
    (r"\bpollution|\bpollutant", 2),
    (r"\benvironment(al)?\b", 2),
    (r"\becosystem", 2),
    (r"\bbiodiversity", 2),
    (r"\bmicroplastic|\bnanoplastic", 2),
    (r"\bdeforestation", 2),
    (r"\bsustainab", 1),
    (r"\bwildfire", 2),
    (r"\bvolcan(o|ic)", 1),
    # Počasí apod. (váha 1)
    (r"\bheat ?wave", 1),
    (r"\bdrought", 1),
    (r"\bclouds?\b", 1),
    (r"\bweather\b", 1),
    # Atmosféry jiných planet a exoplanet
    (r"\bexoplanet\w* atmospher|\bplanetary atmospher", 4),
    (r"\bhazes?\b|\bhazy\b", 3),
    (r"\btholins?\b", 4),
    (r"\bphotochemi", 3),
    (r"\bsulfuric acid cloud|\bsulphuric acid cloud", 4),
    (r"\btransmission spectr|\bemission spectr", 2),
    (r"\bsilicate cloud|\bcondensate cloud|\bcloud deck", 3),
    (r"\bsuper-?rotation|\bjet stream|\bpolar vortex", 2),
]

# Výrazy, podle kterých se článek zařadí do tématu „Jiné planety a vesmír“ (+1 bod).
PLANETARY = re.compile(r"\b(exoplanets?|hot jupiters?|sub-neptunes?|super-earths?|brown dwarfs?|Venus|Venusian|Mars|Martian|"
                       r"Jupiter|Jovian|Saturn|Titan|Uranus|Neptune|Triton|Pluto|Io|Europa|Enceladus|"
                       r"(?i:interstellar|circumstellar|interplanetary|protoplanetary|comets?|asteroids?|meteors?|meteorites?|lunar|regolith|exoplanets?|hot jupiters?)|Moon|"
                       r"JWST|James Webb|TRAPPIST|WASP-\d+|K2-\d+|TOI-\d+|GJ \d+|LHS \d+)\b")
USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 atmo_news/1.0")
TIMEOUT = 20

COMPILED = [(re.compile(p, re.IGNORECASE), w, p) for p, w in KEYWORDS]

# Užší výběr (--narrow): počítají se jen „jádrové“ výrazy – váha ≥ 3 (aerosoly, částice,
# kvalita ovzduší, atmosféra, prach, atmosféry planet…) a všechny výrazy týkající se prachu.
# Obecná slova jako climate, environment, pollution, weather se ignorují.
NARROW_DAYS = 30
NARROW_MIN_SCORE = 6
COMPILED_NARROW = [c for c in COMPILED if c[1] >= 3 or "dust" in c[2]]


# ---------------------------------------------------------------------------
# Stahování kanálů
# ---------------------------------------------------------------------------
def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                               "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, text/html;q=0.8, */*;q=0.5"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def discover_feed(homepage):
    """Najde odkaz na RSS/Atom v HTML hlavičce domovské stránky."""
    try:
        page = http_get(homepage).decode("utf-8", errors="ignore")
    except Exception:
        return None
    for tag in re.findall(r"<link\b[^>]*>", page, re.IGNORECASE):
        if re.search(r"application/(rss|atom)\+xml", tag, re.IGNORECASE):
            m = re.search(r'href\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
            if m:
                return urljoin(homepage, html.unescape(m.group(1)))
    return None


def parse(url):
    data = http_get(url)
    feed = feedparser.parse(data)
    if not feed.entries:
        raise ValueError("kanál neobsahuje žádné položky")
    return feed


def fetch_source(name, url, homepage):
    """Vrátí (name, použitá_url, entries, chyba)."""
    try:
        return name, url, parse(url).entries, None
    except Exception as e:
        first_err = e
    alt = discover_feed(homepage) if homepage else None
    if alt and alt != url:
        try:
            return name, alt, parse(alt).entries, None
        except Exception as e:
            return name, alt, [], f"{first_err}; dohledaný kanál: {e}"
    return name, url, [], str(first_err)


# ---------------------------------------------------------------------------
# Hodnocení
# ---------------------------------------------------------------------------
def strip_html(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", html.unescape(s)).strip()


def score_text(title, summary, narrow=False):
    score, hits = 0, []
    for rx, w, pat in (COMPILED_NARROW if narrow else COMPILED):
        in_title = bool(rx.search(title))
        in_sum = bool(rx.search(summary))
        if in_title or in_sum:
            score += w * (2 if in_title else 1)
            m = rx.search(title) or rx.search(summary)
            hits.append(m.group(0).strip())
    # unikátní, zachovat pořadí
    seen, uniq = set(), []
    for h in hits:
        k = h.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    planet = PLANETARY.search(title) or PLANETARY.search(summary)
    if planet:
        score += 1
        uniq.append(planet.group(0))
    return score, uniq, bool(planet)


def entry_date(e):
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = e.get(key)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def norm_title(t):
    return re.sub(r"[^\w]+", " ", t.lower()).strip()


# ---------------------------------------------------------------------------
# Výstupy
# ---------------------------------------------------------------------------
def highlight(text, terms):
    out = html.escape(text)
    for t in sorted(terms, key=len, reverse=True):
        out = re.sub("(" + re.escape(html.escape(t)) + ")", r"<mark>\1</mark>", out, flags=re.IGNORECASE)
    return out


def local_date(dt):
    """Datum v českém čase (GitHub běží v UTC)."""
    try:
        from zoneinfo import ZoneInfo
        return dt.astimezone(ZoneInfo("Europe/Prague")).strftime("%Y-%m-%d")
    except Exception:
        return dt.astimezone().strftime("%Y-%m-%d")


def write_html(path, articles, status, args):
    sources = sorted({a["source"] for a in articles})
    rows = {"Primární": [], "Popularizační": []}
    for a in articles:
        date = local_date(a["seen"])
        pub = a["date"].strftime("%Y-%m-%d") if a["date"] else "neuvedeno"
        summ = a["summary"][:400] + ("…" if len(a["summary"]) > 400 else "")
        rows[a["kind"]].append(f"""
<article class="card" data-src="{html.escape(a['source'])}" data-topic="{a['topic']}" data-kind="{a['kind']}" data-date="{a['seen'].isoformat()}" data-score="{a['score']}">
  <div class="meta"><span class="score s{min(a['score']//5,4)}">{a['score']}</span>
    <span class="kind k{1 if a['kind']=='Primární' else 2}">{'Primární' if a['kind']=='Primární' else 'Popularizační'}</span>
    <span class="topic t{1 if a['topic']=='Země' else 2}">{a['topic']}</span> <span class="src">{html.escape(a['source'])}</span> · <span title="datum vydání: {pub}">staženo {date}</span>{' · <span class="new">nové</span>' if a.get('is_new') else ''}</div>
  <h2><a href="{html.escape(a['link'])}" target="_blank" rel="noopener">{highlight(a['title'], a['hits'])}</a></h2>
  <p>{highlight(summ, a['hits'])}</p>
  <div class="tags">{''.join(f'<span>{html.escape(h)}</span>' for h in a['hits'])}</div>
</article>""")
    ok = sum(1 for s in status if not s["error"])
    status_rows = "".join(
        f"<tr><td>{html.escape(s['name'])}</td><td>{'✔' if not s['error'] else '✖'}</td>"
        f"<td>{s['n']}</td><td class='err'>{html.escape(s['error'] or '')}</td>"
        f"<td><a href='{html.escape(s['url'])}'>kanál</a></td></tr>" for s in status)
    opts = "".join(f"<option>{html.escape(s)}</option>" for s in sources)
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("Europe/Prague")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if args.publish:  # webová verze: odkazy mezi variantami + „aplikace“ na ploše mobilu
        cur = "uzky" if args.narrow else "index"
        nav = ('<nav class="nav">'
               f'<a href="index.html" class="{"on" if cur == "index" else ""}">Široký výběr · 7 dní</a>'
               f'<a href="uzky.html" class="{"on" if cur == "uzky" else ""}">Užší výběr · 30 dní</a>'
               f'<a href="{cur}.csv">CSV</a></nav>')
        pwa = ('<link rel="manifest" href="manifest.json"><meta name="theme-color" content="#1f6feb">'
               '<link rel="icon" href="icon-192.png"><link rel="apple-touch-icon" href="icon-192.png">')
    else:
        nav = pwa = ""
    doc = f"""<!DOCTYPE html>
<html lang="cs"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">{pwa}
<title>Atmosféra & aerosoly – přehled článků {now}</title>
<style>
 :root {{ --bg:#f7f8fa; --fg:#1d2330; --mut:#667085; --card:#fff; --line:#e4e7ec; --acc:#1f6feb; }}
 @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0f1218; --fg:#e6e9ef; --mut:#98a2b3; --card:#171b23; --line:#2a303c; --acc:#5b9dff; }} }}
 body {{ margin:0; font:15px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif; background:var(--bg); color:var(--fg); }}
 header {{ padding:24px 20px 8px; max-width:960px; margin:auto; }}
 h1 {{ margin:0 0 4px; font-size:22px; }}
 .sub {{ color:var(--mut); font-size:13px; }}
 .bar {{ display:flex; gap:8px; flex-wrap:wrap; margin:14px 0 4px; }}
 .bar input,.bar select {{ padding:7px 10px; border:1px solid var(--line); border-radius:8px; background:var(--card); color:var(--fg); font:inherit; }}
 .bar input[type=search] {{ flex:1; min-width:200px; }}
 main {{ max-width:960px; margin:auto; padding:0 20px 40px; }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:14px 16px; margin:10px 0; }}
 .card h2 {{ font-size:17px; margin:4px 0 6px; }}
 .card a {{ color:var(--fg); text-decoration:none; }} .card a:hover {{ color:var(--acc); text-decoration:underline; }}
 .card p {{ margin:0 0 8px; color:var(--mut); }}
 .meta {{ font-size:12px; color:var(--mut); }}
 .score {{ display:inline-block; min-width:22px; text-align:center; border-radius:6px; padding:0 5px; font-weight:600; color:#fff; margin-right:6px; }}
 .s0 {{ background:#98a2b3; }} .s1 {{ background:#3e9b6d; }} .s2 {{ background:#2f80c9; }} .s3 {{ background:#7a4fd6; }} .s4 {{ background:#c2410c; }}
 .topic {{ font-size:11px; border-radius:4px; padding:0 6px; margin-right:4px; }} .t1 {{ background:#dcfce7; color:#166534; }} .t2 {{ background:#ede9fe; color:#5b21b6; }}
 .new {{ color:#c2410c; font-weight:600; }}
 .tags span {{ display:inline-block; font-size:11px; border:1px solid var(--line); border-radius:999px; padding:1px 8px; margin:2px 4px 0 0; color:var(--mut); }}
 mark {{ background:#fde68a; color:inherit; padding:0 1px; border-radius:2px; }}
 @media (prefers-color-scheme: dark) {{ mark {{ background:#665200; }} }}
 details {{ margin-top:30px; font-size:13px; }}
 table {{ border-collapse:collapse; width:100%; }} td {{ border-bottom:1px solid var(--line); padding:4px 6px; vertical-align:top; }}
 td.err {{ color:#c2410c; font-size:12px; }}
 #count {{ color:var(--mut); font-size:13px; }}
 .nav {{ display:flex; gap:6px; margin-bottom:12px; flex-wrap:wrap; }}
 .nav a {{ font-size:13px; padding:5px 12px; border-radius:999px; border:1px solid var(--line); color:var(--fg); text-decoration:none; background:var(--card); }}
 .nav a.on {{ background:var(--acc); border-color:var(--acc); color:#fff; }}
 .tblwrap {{ overflow-x:auto; }}
 @media (max-width:640px) {{
   header {{ padding:16px 12px 6px; }} main {{ padding:0 12px 30px; }} h1 {{ font-size:19px; }}
   .bar select {{ flex:1 1 45%; min-width:0; }} .bar input[type=search] {{ flex:1 1 100%; }}
   .card {{ padding:12px; }} .card h2 {{ font-size:16px; }}
 }}
 .chk {{ display:flex; align-items:center; gap:6px; font-size:14px; padding:0 4px; }}
 .sec h3 {{ font-size:15px; margin:22px 0 4px; padding-bottom:4px; border-bottom:2px solid var(--line); }}
 .sec h3 .cnt {{ color:var(--mut); font-weight:400; }}
 .kind {{ font-size:11px; border-radius:4px; padding:0 6px; margin-right:4px; font-weight:600; }}
 .k1 {{ background:#dbeafe; color:#1e40af; }} .k2 {{ background:#fef3c7; color:#92400e; }}
</style></head><body>
<header>
 {nav}
 <h1>Atmosféra, aerosoly & životní prostředí – Země i jiné planety</h1>
 <div class="sub">Vygenerováno {now} · režim: {"užší výběr" if args.narrow else "široký výběr"} · období: posledních {args.days} dní · min. skóre {args.min_score} ·
 zdroje: {ok}/{len(status)} funkčních · článků: {len(articles)}</div>
 <div class="bar">
  <input type="search" id="q" placeholder="Hledat v titulcích a popisech…">
  <select id="topic"><option value="">Země i vesmír</option><option>Země</option><option>Jiné planety a vesmír</option></select>
  <select id="src"><option value="">Všechny zdroje</option>{opts}</select>
  <select id="min"><option value="0">Jakékoli skóre</option><option value="5">skóre ≥ 5</option><option value="8">skóre ≥ 8</option><option value="12">skóre ≥ 12</option></select>
  <select id="kind"><option value="">Primární i popularizační</option><option value="Primární">Jen primární (časopisy)</option><option value="Popularizační">Jen popularizační</option></select>
  <label class="chk"><input type="checkbox" id="split" {"checked" if args.split else ""}> Rozdělit na primární / popularizační</label>
  <select id="sort"><option value="date">Řadit podle data stažení</option><option value="score">Řadit podle skóre</option></select>
 </div>
 <div id="count"></div>
</header>
<main id="list">{'' if articles else '<p>Žádné relevantní články nenalezeny.</p>'}
<section id="secP" class="sec"><h3>Primární zdroje – vědecké časopisy <span class="cnt"></span></h3><div class="cards">{''.join(rows['Primární'])}</div></section>
<section id="secS" class="sec"><h3>Sekundární zdroje – popularizační weby a tiskové zprávy <span class="cnt"></span></h3><div class="cards">{''.join(rows['Popularizační'])}</div></section>
<section id="secA" class="sec" style="display:none"><div class="cards"></div></section>
<details><summary>Stav zdrojů</summary>
<div class="tblwrap"><table><tr><td><b>Zdroj</b></td><td></td><td><b>Položek</b></td><td><b>Chyba</b></td><td></td></tr>{status_rows}</table></div>
</details></main>
<script>
const cards=[...document.querySelectorAll('.card')];
const $=id=>document.getElementById(id);
function upd(){{
 const q=$('q').value.toLowerCase(), s=$('src').value, t=$('topic').value, k=$('kind').value, m=+$('min').value; let n=0;
 cards.forEach(c=>{{ const ok=(!s||c.dataset.src===s)&&(!t||c.dataset.topic===t)&&(!k||c.dataset.kind===k)&&(+c.dataset.score>=m)&&(!q||c.textContent.toLowerCase().includes(q));
   c.style.display=ok?'':'none'; if(ok)n++; }});
 $('count').textContent='Zobrazeno: '+n;
 ['secP','secS'].forEach(id=>{{ const vis=[...$(id).querySelectorAll('.card')].filter(c=>c.style.display!=='none').length;
   $(id).querySelector('.cnt').textContent='('+vis+')'; if($('split').checked) $(id).style.display=vis?'':'none'; }});
}}
function layout(){{
 const split=$('split').checked, by=$('sort').value;
 const sorted=[...cards].sort((a,b)=> by==='score' ? (+b.dataset.score - +a.dataset.score) || b.dataset.date.localeCompare(a.dataset.date)
                                         : b.dataset.date.slice(0,10).localeCompare(a.dataset.date.slice(0,10)) || (+b.dataset.score - +a.dataset.score));
 sorted.forEach(c=>{{ const tgt = !split ? 'secA' : (c.dataset.kind==='Primární' ? 'secP' : 'secS'); $(tgt).querySelector('.cards').appendChild(c); }});
 $('secA').style.display=split?'none':''; $('secP').style.display=split?'':'none'; $('secS').style.display=split?'':'none';
 upd();
}}
['q','src','min','topic','kind'].forEach(id=>$(id).addEventListener('input',upd));
['sort','split'].forEach(id=>$(id).addEventListener('change',layout));
layout();
</script></body></html>"""
    path.write_text(doc, encoding="utf-8")


def write_csv(path, articles):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["staženo", "skóre", "typ zdroje", "téma", "datum vydání", "zdroj", "titulek", "odkaz", "klíčová slova", "popis"])
        for a in articles:
            w.writerow([local_date(a["seen"]), a["score"], a["kind"], a["topic"], a["date"].strftime("%Y-%m-%d") if a["date"] else "",
                        a["source"], a["title"], a["link"], ", ".join(a["hits"]), a["summary"][:500]])


# ---------------------------------------------------------------------------
# 3) CROSSREF – úplný seznam článků časopisů za zvolené období
#    (RSS kanály časopisů obsahují jen aktuální číslo / posledních pár desítek položek,
#    Crossref vrátí všechny články vydané v daném období).
#    (název – stejný jako v FEEDS, aby se zdroje sloučily; ISSN)
# ---------------------------------------------------------------------------
CROSSREF_JOURNALS = [
    ("Nature", "1476-4687"),
    ("Nature Geoscience", "1752-0908"),
    ("Nature Climate Change", "1758-6798"),
    ("Nature Communications", "2041-1723"),
    ("npj Climate and Atmospheric Science", "2397-3722"),
    ("Nature Astronomy", "2397-3366"),
    ("Science", "1095-9203"),
    ("Science Advances", "2375-2548"),
    ("PNAS", "1091-6490"),
    ("Atmospheric Chemistry and Physics", "1680-7324"),
    ("Aerosol Research", "2940-3391"),
    ("Environmental Science & Technology", "1520-5851"),
    ("Journal of Aerosol Science", "0021-8502"),
    ("Atmospheric Environment", "1352-2310"),
    ("Icarus", "0019-1035"),
    ("JGR: Planets", "2169-9100"),
    ("The Planetary Science Journal", "2632-3338"),
]
# Primární zdroje = vědecké časopisy (recenzované články). Vše ostatní (weby, magazíny,
# tiskové zprávy EurekAlert!, AAS Nova…) je sekundární / popularizační.
# Přidáte-li do FEEDS další časopis, doplňte sem jeho název.
PRIMARY_SOURCES = {name for name, _ in CROSSREF_JOURNALS}


def source_kind(name):
    return "Primární" if name in PRIMARY_SOURCES else "Popularizační"


# Volitelné: váš e-mail – Crossref pak dotazy obsluhuje přednostně („polite pool“).
CROSSREF_MAILTO = os.environ.get("CROSSREF_MAILTO", "")
CROSSREF_TIMEOUT = 60
ARCHIVE_KEEP_DAYS = 180   # jak dlouho držet články v archivu


def _cr_date(item):
    for key in ("published-online", "published-print", "published", "issued", "created"):
        parts = (item.get(key) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            p = list(parts[0]) + [1, 1]
            try:
                return datetime(int(p[0]), int(p[1]), int(p[2]), tzinfo=timezone.utc)
            except Exception:
                continue
    return None


def fetch_crossref(name, issn, days):
    """Vrátí (name, url, records, chyba) – všechny články časopisu za posledních `days` dní."""
    from urllib.parse import urlencode
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    base_url = f"https://api.crossref.org/journals/{issn}/works"
    params = {"filter": f"from-pub-date:{since},type:journal-article", "rows": 500,
              "select": "DOI,title,abstract,URL,published-online,published-print,published,issued,created",
              "cursor": "*"}
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    records, url = [], base_url + "?" + urlencode({k: v for k, v in params.items() if k != "cursor"})
    try:
        for _ in range(20):  # max 10 000 položek
            req = urllib.request.Request(base_url + "?" + urlencode(params),
                                         headers={"User-Agent": "atmo_news/1.0 (" + (CROSSREF_MAILTO or "no-mailto") + ")"})
            with urllib.request.urlopen(req, timeout=CROSSREF_TIMEOUT) as r:
                msg = json.loads(r.read().decode("utf-8"))["message"]
            items = msg.get("items", [])
            for it in items:
                title = strip_html(" ".join(it.get("title") or []))
                doi = (it.get("DOI") or "").lower()
                if not title or not doi:
                    continue
                records.append({"source": name, "title": title, "link": it.get("URL") or f"https://doi.org/{doi}",
                                "doi": doi, "date": _cr_date(it), "summary": strip_html(it.get("abstract", ""))})
            if len(items) < params["rows"] or not msg.get("next-cursor"):
                break
            params["cursor"] = msg["next-cursor"]
        return name, url, records, None
    except Exception as e:
        return name, url, records, str(e)


DOI_RX = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>?#]+)", re.IGNORECASE)


def find_doi(e):
    for key in ("prism_doi", "dc_identifier", "id", "link"):
        v = e.get(key) or ""
        m = DOI_RX.search(v)
        if m:
            return m.group(1).rstrip(".,;)").lower()
    return ""


def rss_records(name, entries):
    out = []
    for e in entries:
        title = strip_html(e.get("title", ""))
        link = e.get("link", "")
        if not title or not link:
            continue
        summary = strip_html(e.get("summary", "") or e.get("description", ""))
        tags = " ".join(t.get("term", "") for t in e.get("tags", []) if isinstance(t, dict))
        out.append({"source": name, "title": title, "link": link, "doi": find_doi(e),
                    "date": entry_date(e), "summary": (summary + " " + tags).strip()})
    return out


# ---------------------------------------------------------------------------
# Archiv – nalezené články se ukládají, takže nezmizí, ani když vypadnou z RSS
# ---------------------------------------------------------------------------
def rec_key(r):
    return "doi:" + r["doi"] if r.get("doi") else "url:" + r["link"]


def load_archive(path):
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    for r in data.values():
        r["date"] = datetime.fromisoformat(r["date"]) if r.get("date") else None
        r["first_seen"] = datetime.fromisoformat(r["first_seen"])
    return data


def save_archive(path, archive):
    limit = datetime.now(timezone.utc) - timedelta(days=ARCHIVE_KEEP_DAYS)
    out = {}
    for k, r in archive.items():
        if r["first_seen"] < limit:
            continue
        rr = dict(r)
        rr["date"] = r["date"].isoformat() if r.get("date") else None
        rr["first_seen"] = r["first_seen"].isoformat()
        out[k] = rr
    path.write_text(json.dumps(out, ensure_ascii=False, indent=0), encoding="utf-8")


# ---------------------------------------------------------------------------
# Hlavní běh
# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Vyhledá články o atmosféře, aerosolech a životním prostředí.")
    ap.add_argument("--days", type=int, default=None, help="stáří článků ve dnech (výchozí 7, s --narrow 30)")
    ap.add_argument("--min-score", type=int, default=None, help="minimální skóre relevance (výchozí 4, s --narrow 6)")
    ap.add_argument("--narrow", action="store_true", help="užší výběr: jen jádro tématu (aerosoly, ovzduší, atmosféra, prach), posledních 30 dní")
    ap.add_argument("--only-new", action="store_true", help="zobrazit jen dosud neviděné články")
    ap.add_argument("--typ", choices=["vse", "primarni", "popularizacni"], default="vse",
                    help="jen primární zdroje (časopisy), jen popularizační, nebo vše (výchozí)")
    ap.add_argument("--no-split", dest="split", action="store_false",
                    help="v reportu nezobrazovat primární a popularizační zdroje odděleně (lze přepnout i v reportu)")
    ap.add_argument("--no-crossref", action="store_true", help="nehledat v databázi Crossref (jen RSS)")
    ap.add_argument("--publish", default=None, metavar="SLOŽKA",
                    help="webová verze: uloží report jako SLOŽKA/index.html (s --narrow uzky.html) bez časové značky")
    ap.add_argument("--out", default=None, help="složka pro výstupy (výchozí: podsložka 'vystupy' vedle skriptu)")
    ap.add_argument("--no-open", action="store_true", help="neotvírat report v prohlížeči")
    ap.add_argument("--workers", type=int, default=8, help="počet paralelních stahování")
    args = ap.parse_args()
    if args.days is None:
        args.days = NARROW_DAYS if args.narrow else 7
    if args.min_score is None:
        args.min_score = NARROW_MIN_SCORE if args.narrow else 4

    base = Path(__file__).resolve().parent
    out_dir = Path(args.out) if args.out else base / "vystupy"
    if not args.publish:
        out_dir.mkdir(parents=True, exist_ok=True)
    # „nové“ se sleduje zvlášť pro široký a užší výběr
    seen_file = base / ("videne_clanky_uzky.json" if args.narrow else "videne_clanky.json")
    seen = set(json.loads(seen_file.read_text(encoding="utf-8"))) if seen_file.exists() else set()
    archive_file = base / "archiv_clanku.json"
    archive = load_archive(archive_file)

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=args.days)
    jobs = [("rss", f) for f in FEEDS]
    if not args.no_crossref:
        jobs += [("crossref", j) for j in CROSSREF_JOURNALS]
    print(f"Stahuji {len(FEEDS)} RSS kanálů" + ("" if args.no_crossref else f" a {len(CROSSREF_JOURNALS)} časopisů z Crossrefu") + "…")
    t0 = time.time()

    status, fresh = [], []
    feed_names = [f[0] for f in FEEDS]
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {}
        for kind, j in jobs:
            if kind == "rss":
                futs[ex.submit(fetch_source, *j)] = kind
            else:
                futs[ex.submit(fetch_crossref, j[0], j[1], args.days)] = kind
        for fut in as_completed(futs):
            kind = futs[fut]
            name, url, items, err = fut.result()
            recs = rss_records(name, items) if kind == "rss" else items
            if kind == "crossref":
                label = f"{name} [Crossref]"
            elif feed_names.count(name) > 1:  # víc kanálů stejného webu – rozlišit rubrikou
                label = f"{name} – {re.sub(r'/?feed$', '', urlparse(url).path.strip('/')) or 'hlavní kanál'}"
            else:
                label = name
            status.append({"name": label, "url": url, "n": len(recs), "error": err})
            print(f"  {'OK ' if not err else 'ERR'} {label:<48} {len(recs):>5} položek" + (f"  ({err[:60]})" if err else ""))
            fresh.extend(recs)

    # Nové relevantní záznamy do archivu (ukládá se s mírným prahem, filtruje se až níže)
    for r in fresh:
        k = rec_key(r)
        if k in archive:
            old = archive[k]
            if len(r["summary"]) > len(old.get("summary", "")):
                old["summary"] = r["summary"]
            if not old.get("date") and r.get("date"):
                old["date"] = r["date"]
            continue
        if score_text(r["title"], r["summary"])[0] >= 3:
            archive[k] = dict(r, first_seen=now)

    # Kandidáti = aktuálně stažené + archiv
    candidates = fresh + [r for r in archive.values()]
    articles, by_key = [], {}
    for r in candidates:
        d = r.get("date")
        if d and d < cutoff:  # vydáno před začátkem období
            continue
        arch = archive.get(rec_key(r))
        fs = (arch or {}).get("first_seen") or r.get("first_seen") or now
        score, hits, planet = score_text(r["title"], r["summary"], args.narrow)
        if score < args.min_score:
            continue
        keys = [k for k in ("doi:" + r["doi"] if r.get("doi") else None, "url:" + r["link"],
                            "t:" + norm_title(r["title"])) if k]
        prev = next((by_key[k] for k in keys if k in by_key), None)
        if prev:  # duplicita – necháme verzi s delším popisem / vyšším skóre
            if score > prev["score"] or (score == prev["score"] and len(r["summary"]) > len(prev["summary"])):
                prev.update(source=r["source"], summary=r["summary"], score=score, hits=hits)
            if not prev["date"] and r.get("date"):
                prev["date"] = r["date"]
            prev["seen"] = min(prev["seen"], fs)
            for k in keys:
                by_key[k] = prev
            continue
        art = {"source": r["source"], "title": r["title"], "link": r["link"], "date": r.get("date"), "seen": fs,
               "summary": r["summary"], "score": score, "hits": hits,
               "is_new": r["link"] not in seen and ("doi:" + r.get("doi", "")) not in seen,
               "topic": "Jiné planety a vesmír" if planet else "Země"}
        for k in keys:
            by_key[k] = art
        articles.append(art)

    # Do období se počítá datum STAŽENÍ (první nález skriptem), ne datum vydání –
    # některé časopisy uvádějí data vydání i měsíce dopředu.
    articles = [a for a in articles if a["seen"] >= cutoff]
    status.sort(key=lambda s: s["name"])
    for a in articles:
        a["kind"] = source_kind(a["source"])
    if args.typ == "primarni":
        articles = [a for a in articles if a["kind"] == "Primární"]
    elif args.typ == "popularizacni":
        articles = [a for a in articles if a["kind"] == "Popularizační"]
    if args.only_new:
        articles = [a for a in articles if a["is_new"]]
    articles.sort(key=lambda a: (a["seen"].date(), a["score"]), reverse=True)  # nejnovější stažené nahoře

    stamp = (datetime.now().strftime("%Y-%m-%d_%H%M") + ("_uzky" if args.narrow else "")
             + {"vse": "", "primarni": "_primarni", "popularizacni": "_popularizacni"}[args.typ])
    html_path = out_dir / f"clanky_{stamp}.html"
    csv_path = out_dir / f"clanky_{stamp}.csv"
    if args.publish:
        pub = Path(args.publish)
        pub.mkdir(parents=True, exist_ok=True)
        page = "uzky" if args.narrow else "index"
        html_path, csv_path = pub / f"{page}.html", pub / f"{page}.csv"
        args.no_open = True
    write_html(html_path, articles, status, args)
    write_csv(csv_path, articles)

    seen |= {a["link"] for a in articles}
    seen_file.write_text(json.dumps(sorted(seen), ensure_ascii=False, indent=0), encoding="utf-8")
    save_archive(archive_file, archive)

    bad = [s["name"] for s in status if s["error"]]
    nprim = sum(1 for a in articles if a["kind"] == "Primární")
    print(f"\nHotovo za {time.time()-t0:.0f} s. Nalezeno {len(articles)} relevantních článků "
          f"({nprim} primárních, {len(articles)-nprim} popularizačních; archiv: {len(archive)} záznamů).")
    if bad:
        print(f"Nefunkční zdroje ({len(bad)}): {', '.join(bad)}  – upravte jejich URL / ISSN.")
    print(f"Report: {html_path}\nCSV:    {csv_path}")
    if not args.no_open:
        webbrowser.open(html_path.as_uri())


if __name__ == "__main__":
    main()
