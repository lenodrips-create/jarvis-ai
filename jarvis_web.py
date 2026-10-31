#!/usr/bin/env python3
"""
Jarvis as a website: serves the page in web/ and does the parts a browser can't
(the AI key from keys.txt, Ryan's Piper voice) on your own computer.

Start it by double-clicking "Start Jarvis.command" (Mac), or run:
    python jarvis_web.py
then it opens http://localhost:8765 in your browser.
"""

import datetime
import difflib
import html
import io
import json
import os
import re
import subprocess
import sys
import threading
import urllib.parse
import urllib.request
import wave
import webbrowser
import xml.etree.ElementTree as ET
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import assistant          # loads keys.txt and certificates; holds Brain and Voice

VERSION = "v31 (Oct 31)"     # shown on the page and in the Terminal, to check which copy is running
PORT = int(os.environ.get("JARVIS_PORT", "8765"))
WEB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
# The song for the "two claps" / "jarvis music" command. Swap in any MP3 with this name.
MUSIC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music.mp3")

# "hey jarvis open <name>": these names do something specific; anything else opens
# the app in your Applications folder whose name matches best.
# "open hub" shows your repositories when GITHUB_USER=yourname is in keys.txt
# (github.com's own home page now leads with Copilot).
GITHUB_USER = re.sub(r"[^A-Za-z0-9-]", "", os.environ.get("GITHUB_USER", ""))
GITHUB_URL = f"https://github.com/{GITHUB_USER}?tab=repositories" if GITHUB_USER else "https://github.com/"

# Spoken names are also matched by sound, so "clod" or "cloud" still finds Claude.
OPEN_SHORTCUTS = {
    "claude": {"app": "Claude", "say": "Claude"},
    "claude desktop": {"app": "Claude", "say": "Claude"},
    "hub": {"url": GITHUB_URL, "browser": "Google Chrome", "say": "GitHub"},
    "github": {"url": GITHUB_URL, "browser": "Google Chrome", "say": "GitHub"},
}
APP_DIRS = ["/Applications", "/System/Applications", "/System/Applications/Utilities",
            os.path.expanduser("~/Applications")]

# "what's the weather" / "good morning". Open-Meteo is free and needs no account or key.
# Change these in keys.txt (e.g. JARVIS_NAME=..., WEATHER_PLACE=..., WEATHER_LAT=..., WEATHER_LON=...).
OWNER_NAME = assistant.OWNER_NAME
WEATHER_PLACE = os.environ.get("WEATHER_PLACE", "Greencastle")          # Greencastle, PA 17225
WEATHER_LAT = float(os.environ.get("WEATHER_LAT", "39.7904"))
WEATHER_LON = float(os.environ.get("WEATHER_LON", "-77.7275"))
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# World Meteorological Organization weather codes, as Open-Meteo reports them.
SKY = {0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "cloudy", 45: "foggy", 48: "foggy",
       51: "drizzling", 53: "drizzling", 55: "drizzling", 56: "drizzling and icy", 57: "drizzling and icy",
       61: "rainy", 63: "rainy", 65: "pouring rain", 66: "freezing rain", 67: "freezing rain",
       71: "snowy", 73: "snowy", 75: "snowing heavily", 77: "snowy",
       80: "showery", 81: "showery", 82: "pouring rain", 85: "snow showers", 86: "snow showers",
       95: "stormy", 96: "stormy with hail", 99: "stormy with hail"}

# "what's the news": Fox News's own feeds, newest first, with
# the homepage as a last resort.
NEWS_FEEDS = ["https://moxie.foxnews.com/google-publisher/latest.xml",
              "https://feeds.foxnews.com/foxnews/latest"]
NEWS_HOME = "https://www.foxnews.com/"

# "what's going on with my NFL team": ESPN's public sports data. NFL_TEAM in keys.txt
# takes ESPN's short team code (cin = Cincinnati Bengals).
NFL_TEAM = os.environ.get("NFL_TEAM", "cin").strip().lower()
ESPN_NFL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

# "hey jarvis search for ...": a short spoken answer from DuckDuckGo or Wikipedia (free, no
# account), plus the full results opened in Chrome.
DDG_URL = "https://api.duckduckgo.com/"
WIKI_URL = "https://en.wikipedia.org"
SEARCH_PAGE = "https://www.google.com/search?q="

# Finance: live prices from Yahoo Finance's public chart data (Stooq as a backup), and the
# headlines from Goldman Sachs's Markets insights page.
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/"
YAHOO_SEARCH = "https://query2.finance.yahoo.com/v1/finance/search"
STOOQ_URL = "https://stooq.com/q/l/"
GS_INSIGHTS = "https://www.goldmansachs.com/insights/markets"
INDEXES = [("^GSPC", "The S&P 500"), ("^DJI", "The Dow"), ("^IXIC", "The Nasdaq")]
TICKERS = {"apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT", "amazon": "AMZN", "google": "GOOGL",
           "alphabet": "GOOGL", "nvidia": "NVDA", "meta": "META", "facebook": "META", "netflix": "NFLX",
           "goldman sachs": "GS", "goldman": "GS", "disney": "DIS", "coca cola": "KO", "coke": "KO",
           "walmart": "WMT", "nike": "NKE", "ford": "F", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
           "s&p 500": "^GSPC", "s and p 500": "^GSPC", "the dow": "^DJI", "dow": "^DJI", "nasdaq": "^IXIC"}

# News and sports sites often refuse requests that don't look like a browser.
BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 jarvis-voice-assistant/1.0")

# Talking with Jarvis: on when an AI key (ANTHROPIC_API_KEY, GROQ_API_KEY or GEMINI_API_KEY)
# is in keys.txt, otherwise Jarvis only does his commands. AI_ANSWERS=on / off overrides
# that (on with no key uses Ollama on your Mac).
_ai_setting = os.environ.get("AI_ANSWERS", "auto").strip().lower()
AI_KEY_SET = bool(assistant.ANTHROPIC_API_KEY or assistant.GROQ_API_KEY or assistant.GEMINI_API_KEY)
AI_ANSWERS = _ai_setting in ("on", "yes", "true", "1") or (_ai_setting == "auto" and AI_KEY_SET)
NOT_A_COMMAND = "That's not one of my commands."

_brain = None
_brain_lock = threading.Lock()
_piper = None
_piper_error = None
_piper_lock = threading.Lock()


def get_brain():
    """The AI conversation (one shared memory). Raises RuntimeError with a readable message."""
    global _brain
    with _brain_lock:
        if _brain is None:
            try:
                _brain = assistant.Brain()
            except SystemExit as e:             # Brain explains missing keys via sys.exit
                raise RuntimeError(str(e)) from None
        return _brain


def get_piper():
    """Ryan's voice, downloaded once. None if it can't be loaded (the page then uses the browser's voice)."""
    global _piper, _piper_error
    with _piper_lock:
        if _piper is None and _piper_error is None:
            try:
                _piper = assistant.load_piper()
            except Exception as e:
                _piper_error = str(e)
                print(f"[Piper voice unavailable, the page will use the browser's voice: {e}]", file=sys.stderr)
        return _piper


_speak_lock = threading.Lock()


def synthesize_wav(text):
    out = io.BytesIO()
    with _speak_lock, wave.open(out, "wb") as w:   # one sentence at a time (the page may ask ahead)
        get_piper().synthesize_wav(text, w)
    return out.getvalue()


_fish = None


def voice_in_use():
    """("fish" or "ryan" or None, a sentence explaining it) for the status label and the Terminal."""
    if assistant.FISH_API_KEY:
        try:
            import fish_audio_sdk  # noqa: F401
            return "fish", f"Voice: Fish Audio ({assistant.FISH_VOICE_ID}). If a sentence fails, Ryan says it instead."
        except ImportError:
            reason = "Fish Audio key found, but the fish-audio-sdk package isn't installed (run Start Jarvis again)"
            return ("ryan" if get_piper() else None), f"Voice: Ryan. {reason}."
    return ("ryan" if get_piper() else None), "Voice: Ryan (no FISH_API_KEY in keys.txt)."


def synthesize_fish(text):
    """Jarvis's Fish Audio voice as MP3 bytes (needs FISH_API_KEY in keys.txt)."""
    global _fish
    from fish_audio_sdk import Session, TTSRequest
    if _fish is None:
        _fish = Session(assistant.FISH_API_KEY)
    req = TTSRequest(text=text, reference_id=assistant.FISH_VOICE_ID, format="mp3")
    return b"".join(_fish.tts(req, backend=assistant.FISH_MODEL))


def _simplify(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def installed_apps():
    """{display name: path} for the .app bundles in the usual Applications folders."""
    apps = {}
    for folder in APP_DIRS:
        try:
            for entry in os.listdir(folder):
                if entry.endswith(".app"):
                    apps.setdefault(entry[:-4], os.path.join(folder, entry))
        except OSError:
            pass
    return apps


def sound_key(name):
    """A rough "sounds like" key: clod, cloud, clawed and Claude all become "kld"."""
    w = _simplify(name)
    for a, b in (("ph", "f"), ("ck", "k"), ("gh", ""), ("dg", "j"), ("qu", "kw"), ("x", "ks"),
                 ("c", "k"), ("q", "k"), ("z", "s")):
        w = w.replace(a, b)
    if not w:
        return ""
    w = w[0] + re.sub(r"[aeiouwhy]", "", w[1:])               # keep consonants after the first letter
    return re.sub(r"(.)\1+", r"\1", w)                        # "ll" -> "l"


def best_match(spoken, names):
    """The name in `names` that best matches what was heard, or None."""
    by_key = {_simplify(n): n for n in names}
    want = _simplify(spoken)
    if not want:
        return None
    if want in by_key:                                          # "safari" -> Safari
        return by_key[want]
    for key, n in sorted(by_key.items(), key=lambda kv: len(kv[0])):
        if len(want) >= 3 and (key.startswith(want) or want in key):   # "chrome" -> Google Chrome
            return n
    heard = sound_key(spoken)
    sounds, word_sounds = {}, {}
    for n in names:
        sounds.setdefault(sound_key(n), n)
        for word in n.split():
            if len(word) >= 3:                                  # "Jon" in "Jon Smith"
                word_sounds.setdefault(sound_key(word), n)
    if heard in sounds:                                         # "clod" -> Claude
        return sounds[heard]
    if heard in word_sounds:                                    # "crome" -> Google Chrome
        return word_sounds[heard]
    close = [k for k in difflib.get_close_matches(want, list(by_key), n=3, cutoff=0.8)
             if abs(len(k) - len(want)) <= 2]                   # small typos only: not "photoshop" -> Photos
    return by_key[close[0]] if close else None


def find_app(name):
    """Best-matching installed app for a spoken name, as (name, path), or None."""
    apps = installed_apps()
    match = best_match(name, list(apps))
    return (match, apps[match]) if match else None


def open_target(name):
    """Open an app (or a shortcut's website). Returns (ok, what to say)."""
    if sys.platform != "darwin":
        return False, "Opening apps only works on a Mac for now."
    spoken = name.strip().strip(".!?").lower()
    spoken = re.sub(r"^(the|my)\s+", "", spoken)
    spoken = re.sub(r"\s+(app|application)$", "", spoken)
    key = spoken if spoken in OPEN_SHORTCUTS else best_match(spoken, list(OPEN_SHORTCUTS))
    short = OPEN_SHORTCUTS.get(key) if key else None
    if short and "url" in short:
        # Ask macOS for the browser by name; if that fails, use your default browser.
        result = subprocess.run(["open", "-a", short["browser"], short["url"]], check=False, capture_output=True)
        if result.returncode != 0:
            result = subprocess.run(["open", short["url"]], check=False, capture_output=True)
        if result.returncode != 0:
            return False, f"I couldn't open {short['say']}."
        return True, f"Opening {short['say']}."
    found = find_app(short["app"] if short else spoken)
    if not found:
        return False, f"I couldn't find an app called {name.strip()}."
    result = subprocess.run(["open", found[1]], check=False, capture_output=True)
    if result.returncode != 0:
        return False, f"{found[0]} didn't open."
    return True, f"Opening {short['say'] if short else found[0]}."


def get_weather():
    """Current conditions and today's high/low in Fahrenheit for WEATHER_PLACE."""
    query = urllib.parse.urlencode({
        "latitude": WEATHER_LAT, "longitude": WEATHER_LON,
        "current": "temperature_2m,weather_code,is_day",
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit", "timezone": "auto", "forecast_days": 1,
    })
    req = urllib.request.Request(f"{WEATHER_URL}?{query}", headers={"User-Agent": "jarvis-voice-assistant/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    now, today = data["current"], data["daily"]
    sky = SKY.get(now["weather_code"], "unsettled")
    if sky == "clear" and now.get("is_day"):
        sky = "sunny"
    return {"sky": sky, "temp": round(now["temperature_2m"]),
            "high": round(today["temperature_2m_max"][0]), "low": round(today["temperature_2m_min"][0])}


def weather_sentence(kind):
    try:
        w = get_weather()
    except Exception as e:
        print(f"[weather unavailable: {e}]", file=sys.stderr)
        return "Sorry, I couldn't get the weather right now."
    if kind == "morning":
        hello = f"Good morning, {OWNER_NAME}." if OWNER_NAME else "Good morning."
        return f"{hello} The weather is {w['sky']} and the temperature is {w['temp']} degrees."
    return (f"Right now in {WEATHER_PLACE} it's {w['sky']} and {w['temp']} degrees, "
            f"with a high of {w['high']} and a low of {w['low']} today.")


def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _clean(text):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", text or ""))).strip()


def top_headlines(n=5):
    """The newest Fox News headlines."""
    for url in NEWS_FEEDS:
        try:
            root = ET.fromstring(fetch(url))
        except Exception as e:
            print(f"[news feed {url} unavailable: {e}]", file=sys.stderr)
            continue
        titles = [_clean(item.findtext("title")) for item in root.iter("item")]
        titles = list(dict.fromkeys(t for t in titles if t))
        if titles:
            return titles[:n]
    try:                                                    # last resort: the homepage
        page = fetch(NEWS_HOME).decode("utf-8", "replace")
        found = re.findall(r'<h[23] class="title[^"]*">\s*<a [^>]*>(.*?)</a>', page, re.S)
        return list(dict.fromkeys(t for t in map(_clean, found) if len(t) > 15))[:n]
    except Exception as e:
        print(f"[news homepage unavailable: {e}]", file=sys.stderr)
        return []


ORDINALS = ["First", "Second", "Third", "Fourth", "Fifth", "Sixth", "Seventh"]


def _sentence(text):
    """End with exactly one full stop (or keep the ? / !)."""
    text = text.strip().rstrip(".")
    return text if text.endswith(("?", "!")) else text + "."


def news_sentence():
    titles = top_headlines(5)
    if not titles:
        return "Sorry, I couldn't get the news right now."
    stories = " ".join(f"{ORDINALS[i]}: {_sentence(t)}" for i, t in enumerate(titles))
    return f"Here are the top {len(titles)} stories from Fox News. {stories}"


def _spoken_record(summary):
    return " and ".join(summary.split("-"))                 # "5-3" -> "5 and 3"


def _spoken_when(iso):
    try:
        when = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
    except (ValueError, AttributeError):
        return ""
    hour = when.strftime("%I").lstrip("0")
    minute = when.strftime(":%M") if when.minute else ""
    return f"{when.strftime('%A, %B')} {when.day} at {hour}{minute} {when.strftime('%p')}"


def nfl_sentence():
    try:
        team = json.loads(fetch(f"{ESPN_NFL}/teams/{NFL_TEAM}"))["team"]
    except Exception as e:
        print(f"[ESPN unavailable: {e}]", file=sys.stderr)
        return "Sorry, I couldn't reach ESPN right now."
    name = team.get("name") or team.get("shortDisplayName") or "your team"   # "Bengals"
    words = [f"Here's what's going on with the {name}."]
    records = team.get("record", {}).get("items") or []
    total = next((r for r in records if r.get("type") == "total"), records[0] if records else None)
    if total and total.get("summary"):
        standing = team.get("standingSummary")
        words.append(f"They're {_spoken_record(total['summary'])}" + (f", {standing}." if standing else "."))
    upcoming = team.get("nextEvent") or []
    if upcoming:
        game = upcoming[0]
        when = _spoken_when(game.get("date"))
        words.append(f"Next up: {game.get('name', 'their next game')}" + (f", {when}." if when else "."))
    team_id = str(team.get("id", ""))
    keys = [k.lower() for k in (name, team.get("location"), team.get("displayName")) if k]

    def about_team(a):
        text = f"{a.get('headline', '')} {a.get('description', '')}".lower()
        cats = a.get("categories") or []
        return any(str(c.get("teamId")) == team_id for c in cats) or any(k in text for k in keys)

    headlines = []
    for url in (f"{ESPN_NFL}/news?team={team_id}&limit=25", f"{ESPN_NFL}/news?limit=50"):
        try:
            articles = json.loads(fetch(url)).get("articles", [])
        except Exception:
            continue
        headlines = list(dict.fromkeys(_clean(a.get("headline")) for a in articles if about_team(a) and a.get("headline")))
        if headlines:
            break
    if headlines:
        words.append("In the news: " + " ".join(_sentence(h) for h in headlines[:3]))
    return " ".join(words)


def _first_sentences(text, n=2, limit=320):
    parts = re.split(r"(?<=[.!?])\s+", _clean(text))
    out = " ".join(parts[:n])
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "."


def quick_answer(query):
    """A short spoken answer, or None. DuckDuckGo's instant answers first, then Wikipedia."""
    try:
        q = urllib.parse.urlencode({"q": query, "format": "json", "no_html": 1, "skip_disambig": 1})
        d = json.loads(fetch(f"{DDG_URL}?{q}"))
        for key in ("Answer", "AbstractText", "Definition"):
            if isinstance(d.get(key), str) and d[key].strip():
                return _first_sentences(d[key])
    except Exception as e:
        print(f"[DuckDuckGo unavailable: {e}]", file=sys.stderr)
    try:
        q = urllib.parse.urlencode({"q": query, "limit": 1})
        pages = json.loads(fetch(f"{WIKI_URL}/w/rest.php/v1/search/page?{q}")).get("pages", [])
        if pages:
            title = urllib.parse.quote(pages[0]["key"], safe="")
            summary = json.loads(fetch(f"{WIKI_URL}/api/rest_v1/page/summary/{title}"))
            if summary.get("extract"):
                return _first_sentences(summary["extract"])
    except Exception as e:
        print(f"[Wikipedia unavailable: {e}]", file=sys.stderr)
    return None


def open_in_chrome(url):
    """Open a web page in Google Chrome (or the default browser). True if it opened."""
    if sys.platform != "darwin":
        return False
    return subprocess.run(["open", "-a", "Google Chrome", url], capture_output=True).returncode == 0 \
        or subprocess.run(["open", url], capture_output=True).returncode == 0


def quote(symbol):
    """(name, price, percent change or None) for a ticker symbol."""
    try:
        meta = json.loads(fetch(f"{YAHOO_CHART}{urllib.parse.quote(symbol)}?range=1d&interval=1d"))["chart"]["result"][0]["meta"]
        price = float(meta["regularMarketPrice"])
        prev = meta.get("previousClose") or meta.get("chartPreviousClose")
        change = (price - prev) / prev * 100 if prev else None
        return meta.get("shortName") or meta.get("longName") or symbol, price, change
    except Exception as e:
        print(f"[Yahoo Finance unavailable for {symbol}: {e}]", file=sys.stderr)
    if symbol.startswith("^") or "-" in symbol:
        return None
    try:                                                    # backup: price only
        row = fetch(f"{STOOQ_URL}?s={symbol.lower()}.us&f=sd2t2ohlcv&h&e=csv").decode().splitlines()[1].split(",")
        return symbol, float(row[6]), None
    except Exception as e:
        print(f"[Stooq unavailable for {symbol}: {e}]", file=sys.stderr)
        return None


def _spoken_change(change):
    if change is None:
        return ""
    if abs(change) < 0.05:
        return ", about flat today"
    return f", {'up' if change > 0 else 'down'} {abs(change):.1f} percent today"


def market_sentence():
    parts = []
    for symbol, name in INDEXES:
        q = quote(symbol)
        if q:
            parts.append(f"{name} is at {q[1]:,.0f}{_spoken_change(q[2])}.")
    return ("Here's the market. " + " ".join(parts)) if parts else "Sorry, I couldn't get market prices right now."


def find_ticker(name):
    """(ticker symbol, company name to say) for a spoken company name, or (None, None)."""
    spoken = re.sub(r"^(?:the|a)\s+", "", name.strip().strip(".!?").lower())
    spoken = re.sub(r"\s+(?:stock|shares?|inc|corp|corporation|company)$", "", spoken)
    if spoken in TICKERS:
        return TICKERS[spoken], spoken.title() if not TICKERS[spoken].startswith("^") else None
    try:
        q = urllib.parse.urlencode({"q": spoken, "quotesCount": 1, "newsCount": 0})
        hits = json.loads(fetch(f"{YAHOO_SEARCH}?{q}")).get("quotes", [])
        if hits and hits[0].get("symbol"):
            return hits[0]["symbol"], hits[0].get("shortname") or hits[0].get("longname")
    except Exception as e:
        print(f"[Yahoo Finance search unavailable: {e}]", file=sys.stderr)
    if re.fullmatch(r"[a-z]{1,5}", spoken):                  # "aapl" said as a ticker
        return spoken.upper(), None
    return None, None


def stock_sentence(name):
    symbol, company = find_ticker(name)
    if not symbol:
        return f"I couldn't find a stock called {name.strip()}."
    q = quote(symbol)
    if not q:
        return f"Sorry, I couldn't get the price for {name.strip()} right now."
    label, price, change = q
    label = company or (label if label != symbol else name.strip().title())   # never spell out "PLTR"
    label = re.sub(r"\s+USD$", "", label)                                    # "Bitcoin USD" -> "Bitcoin"
    unit = "points" if symbol.startswith("^") else "dollars"
    amount = f"{price:,.0f}" if price >= 1000 else f"{price:,.2f}"
    return f"{label} is at {amount} {unit}{_spoken_change(change)}."


def insights_sentence():
    """Headlines from Goldman Sachs's Markets insights page, which also opens in Chrome."""
    titles = []
    try:
        page = fetch(GS_INSIGHTS).decode("utf-8", "replace")
        links = re.findall(r'<a[^>]+href="[^"]*/insights/(?:articles|goldman-sachs-research|podcasts)/[^"]+"[^>]*>(.*?)</a>', page, re.S)
        titles = list(dict.fromkeys(t for t in map(_clean, links) if 20 <= len(t) <= 160))[:3]
    except Exception as e:
        print(f"[Goldman Sachs insights unavailable: {e}]", file=sys.stderr)
    opened = open_in_chrome(GS_INSIGHTS)
    if titles:
        heads = " ".join(f"{ORDINALS[i]}: {_sentence(t)}" for i, t in enumerate(titles))
        return f"Here's what Goldman Sachs is saying about the markets. {heads}" + (" I've opened the page in Chrome." if opened else "")
    return "I've opened Goldman Sachs's market insights in Chrome." if opened \
        else "Sorry, I couldn't reach Goldman Sachs's insights right now."


def web_search(query):
    query = query.strip().strip(".!?")
    if not query:
        return "What would you like me to search for?"
    answer = quick_answer(query)
    opened = open_in_chrome(SEARCH_PAGE + urllib.parse.quote_plus(query))
    if answer:
        return answer + (" I've opened the full results in Chrome." if opened else "")
    return f"I've opened the search results for {query}." if opened else f"Sorry, I couldn't find anything on {query}."


# "hey jarvis call ...": look the person up in the Mac's Contacts app (the Mac asks once
# for permission), then hand the number to FaceTime, which calls through your iPhone and
# always shows its own Call button first.
CONTACTS_SCRIPT = """
on run argv
    set mode to item 1 of argv
    set out to ""
    tell application "Contacts"
        if mode is "names" then
            repeat with nm in (name of every person)
                set out to out & nm & linefeed
            end repeat
        else
            repeat with p in (every person whose name is (item 2 of argv))
                repeat with ph in phones of p
                    set out to out & (label of ph) & tab & (value of ph) & linefeed
                end repeat
            end repeat
        end if
    end tell
    return out
end run
"""


def _contacts(*args):
    r = subprocess.run(["osascript", "-e", CONTACTS_SCRIPT, *args], capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise PermissionError(r.stderr.strip())
    return [line for line in r.stdout.splitlines() if line.strip()]


def _spoken_number(digits):
    return " ".join(digits[-10:-7]) + ", " + " ".join(digits[-7:-4]) + ", " + " ".join(digits[-4:]) \
        if len(digits) >= 10 else " ".join(digits)


def call(who):
    """Start a phone call. Returns what Jarvis should say."""
    if sys.platform != "darwin":
        return "Phone calls only work on a Mac."
    who = re.sub(r"^(?:my|the)\s+", "", who.strip().strip(".!?"), flags=re.I)
    who = re.sub(r"\s+(?:please|now|for me|on (?:the )?phone|on facetime)$", "", who, flags=re.I)
    if re.fullmatch(r"[\d\s()+.-]+", who):                 # "717-555-1234"
        name, number = None, re.sub(r"[^0-9+]", "", who)
    else:
        try:
            names = _contacts("names")
            name = best_match(who, names)
            phones = [line.split("\t") for line in _contacts("phones", name)] if name else []
        except (PermissionError, OSError, subprocess.TimeoutExpired) as e:
            print(f"[Contacts unavailable: {e}]", file=sys.stderr)
            return ("I can't see your contacts yet. Allow Terminal to access Contacts in System Settings, "
                    "Privacy and Security, Contacts, then restart Jarvis.")
        if not name:
            return f"I couldn't find {who} in your contacts."
        if not phones:
            return f"{name} doesn't have a phone number in your contacts."
        rank = lambda p: 0 if re.search(r"mobile|iphone|cell", p[0], re.I) else 1
        number = re.sub(r"[^0-9+]", "", sorted(phones, key=rank)[0][-1])
    if len(re.sub(r"[^0-9]", "", number)) < 7:
        return "That doesn't look like a phone number."
    subprocess.run(["open", f"tel://{number}"], capture_output=True)
    return f"Calling {name}." if name else f"Calling {_spoken_number(re.sub(r'[^0-9]', '', number))}."


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass                                     # keep the window quiet

    def _send(self, code, body, content_type):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        if self.path in ("/", "/index.html", "/earth.html"):
            page = "earth.html" if self.path == "/earth.html" else "index.html"
            with open(os.path.join(WEB_DIR, page), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if self.path == "/music.mp3":
            if not os.path.isfile(MUSIC_FILE):
                return self._send(404, b"No music.mp3 in the voice_assistant folder", "text/plain")
            with open(MUSIC_FILE, "rb") as f:
                return self._send(200, f.read(), "audio/mpeg")
        if self.path == "/api/status":
            ai = None
            if AI_ANSWERS:
                try:
                    get_brain()
                except RuntimeError as e:
                    ai = str(e)
            return self._json(200, {"ai_error": ai, "voice": voice_in_use()[0], "version": VERSION})
        self._send(404, b"Not found", "text/plain")

    def do_POST(self):
        # Only this page may use the helper: another website open in your browser
        # must not be able to open apps or talk to the AI behind your back.
        origin = self.headers.get("Origin")
        if origin and origin not in (f"http://localhost:{PORT}", f"http://127.0.0.1:{PORT}"):
            return self._json(403, {"error": "Not allowed"})
        try:
            data = self._body()
        except ValueError:
            return self._json(400, {"error": "Bad request"})
        if self.path == "/api/chat":
            text = str(data.get("text", "")).strip()
            if not text:
                return self._json(400, {"error": "Nothing was said"})
            bye = text.lower().strip(".!? ") in assistant.EXIT_PHRASES
            if not AI_ANSWERS:
                return self._json(200, {"reply": "Goodbye." if bye else NOT_A_COMMAND, "goodbye": bye})
            try:
                reply = get_brain().reply(text)
            except Exception as e:
                return self._json(502, {"error": str(e)})
            return self._json(200, {"reply": reply, "goodbye": bye})
        if self.path == "/api/speak":
            text = str(data.get("text", "")).strip()
            if text and assistant.FISH_API_KEY:     # your Fish Audio voice first, Ryan if it fails
                try:
                    return self._send(200, synthesize_fish(text), "audio/mpeg")
                except Exception as e:
                    print(f"[Fish Audio failed, using Ryan's voice: {e}]", file=sys.stderr)
            if not text or get_piper() is None:
                return self._send(204, b"", "audio/wav")
            try:
                return self._send(200, synthesize_wav(text), "audio/wav")
            except Exception as e:
                print(f"[Piper failed: {e}]", file=sys.stderr)
                return self._send(204, b"", "audio/wav")
        if self.path == "/api/open":
            ok, message = open_target(str(data.get("name", "")))
            return self._json(200, {"ok": ok, "say": message})
        if self.path == "/api/market":
            return self._json(200, {"say": market_sentence()})
        if self.path == "/api/stock":
            return self._json(200, {"say": stock_sentence(str(data.get("name", "")))})
        if self.path == "/api/insights":
            return self._json(200, {"say": insights_sentence()})
        if self.path == "/api/search":
            return self._json(200, {"say": web_search(str(data.get("query", "")))})
        if self.path == "/api/call":
            return self._json(200, {"say": call(str(data.get("who", "")))})
        if self.path == "/api/news":
            return self._json(200, {"say": news_sentence()})
        if self.path == "/api/nfl":
            return self._json(200, {"say": nfl_sentence()})
        if self.path == "/api/weather":
            return self._json(200, {"say": weather_sentence(str(data.get("kind", "now")))})
        if self.path == "/api/reset":
            with _brain_lock:
                if _brain is not None:
                    del _brain.history[1:]       # keep the system prompt, forget the chat
            return self._json(200, {"ok": True})
        self._json(404, {"error": "Not found"})


def main():
    print(f"Starting Jarvis {VERSION} from {os.path.dirname(os.path.abspath(__file__))}")
    print("Getting the voice ready (the first time downloads ~120 MB)...")
    get_piper()
    if AI_ANSWERS:
        try:
            get_brain()                     # first run may download the Ollama AI model here
        except RuntimeError as e:
            print(e)                        # the page shows this too
    print("Talking: " + ("on" if AI_ANSWERS else "off, commands only (add an AI key to keys.txt to talk with Jarvis)"))
    url = f"http://localhost:{PORT}"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:
        print(f"Jarvis is already running. Opening {url}")
        webbrowser.open(url)
        return
    print(voice_in_use()[1])
    print(f"Jarvis is running at {url}  (close this window to stop it)")
    if not os.environ.get("JARVIS_NO_BROWSER"):
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
