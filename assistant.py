#!/usr/bin/env python3
"""
Voice-operated AI assistant.

You talk to it. It talks back. The assistant's answers are spoken only --
nothing it says is printed to the screen, so it is operated entirely by voice.

Pipeline:  microphone  ->  speech-to-text  ->  Ollama  ->  text-to-speech

Backends are chosen automatically from what you have installed:
  * Speech-to-text : Vosk (offline) if a model is present, otherwise Google
                     Web Speech via SpeechRecognition (online, no API key).
  * Brain          : Claude if ANTHROPIC_API_KEY is set, else Groq if
                     GROQ_API_KEY is set (free key), else Google Gemini
                     if GEMINI_API_KEY is set (free key),
                     otherwise a local model via Ollama (free, offline).
  * Text-to-speech : a realistic male Piper neural voice (free, offline;
                     downloaded once on first run), or the Fish Audio voice if
                     FISH_API_KEY is set. Falls back to your OS's built-in voices.

Run:
    ollama pull llama3.2             # once; Ollama from https://ollama.com
    export FISH_API_KEY=...          # optional, for the Fish Audio voice
    python assistant.py

Say "goodbye", "exit" or "stop listening" to quit. Press Ctrl+C any time.
"""

import os
import sys
import json

# --- Configuration -----------------------------------------------------------

# Settings can also go in keys.txt next to this file, one per line, e.g.
#   GROQ_API_KEY=gsk_...
# so you don't have to `export` them in every new terminal window.
import re

KEYS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.txt")
KEYS_LOADED = []          # names read from keys.txt, for the "No AI available" hint


def _load_keys_file(path):
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    waiting = None        # a NAME= line with nothing after it; the value may be on the next line
    for line in text.splitlines():
        # TextEdit can save as rich text (RTF): drop control words like \f0\fs24.
        line = re.sub(r"^(\\[a-zA-Z]+-?\d*\s?|[{}])+", "", line).strip()
        line = re.sub(r"^export\s+", "", line)
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if not sep:
            name, value = waiting, line
        name = (name or "").strip()
        value = value.strip().rstrip("\\}").strip().strip("\"'\u201c\u201d\u2018\u2019 ")
        waiting = name if sep and not value else None
        if value and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            os.environ.setdefault(name, value)
            KEYS_LOADED.append(name)


if os.path.isfile(KEYS_FILE):
    _load_keys_file(KEYS_FILE)

# Python from python.org on macOS ships without trusted certificates until you
# run "Install Certificates.command"; use certifi's bundle so downloads and API
# calls work either way.
try:
    import certifi
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
except ImportError:
    pass

MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")    # any model from `ollama list`
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

# Optional: use Claude instead of Ollama. Key: https://console.anthropic.com (paid).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")

# Optional: use Groq instead of Ollama (free key, very fast). Key: https://console.groq.com/keys
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1"

# Optional: use Google Gemini instead of Ollama. Free key: https://aistudio.google.com/apikey
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")   # always Google's current Flash
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta"
VOSK_MODEL_DIR = os.environ.get("VOSK_MODEL", "model")   # path to an unpacked Vosk model

# Free realistic voice (Piper, offline). Other male voices: en_GB-alan-medium
# (British), en_US-joe-medium, en_GB-northern_english_male-medium.
PIPER_VOICE = os.environ.get("PIPER_VOICE", "en_US-ryan-high")
PIPER_DIR = os.environ.get("PIPER_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices"))

# Fish Audio voice (https://fish.audio). Optional and paid; when FISH_API_KEY is
# set it is used instead of Piper.
FISH_API_KEY = os.environ.get("FISH_API_KEY")
FISH_VOICE_ID = os.environ.get("FISH_VOICE_ID", "612b878b113047d9a770c069c8b4fdfe")
FISH_MODEL = os.environ.get("FISH_MODEL", "s1")

EXIT_PHRASES = {"goodbye", "exit", "quit", "stop listening", "shut down"}

OWNER_NAME = os.environ.get("JARVIS_NAME", "").strip()      # optional: JARVIS_NAME=... in keys.txt

SYSTEM_PROMPT = (
    "Your name is Jarvis. You are a friendly, witty personal voice assistant, in the "
    f"spirit of the AI from Iron Man, and you work for {OWNER_NAME or 'the user'}. People talk to you "
    "by saying \"Hey Jarvis\" or \"Jarvis\": that is your name, so answer naturally and "
    "never say it isn't your name. Speech recognition sometimes mishears your name as "
    "Travis, Charles or similar; treat those as Jarvis too. You are knowledgeable about finance, "
    "markets and investing, and explain them clearly, but you are not a licensed financial adviser, "
    "so you don't tell people what to buy or sell. Your replies are read aloud by a "
    "text-to-speech engine, so keep them short, natural and conversational -- "
    "usually one or two sentences. Never use markdown, bullet points, emoji, "
    "code blocks or symbols that sound strange when spoken. Just talk like a person."
)


# --- Text to speech (the only way the assistant communicates) ----------------

def load_piper():
    """Load the Piper voice, downloading it the first time (~60-120 MB)."""
    from pathlib import Path
    from piper import PiperVoice
    model = Path(PIPER_DIR) / f"{PIPER_VOICE}.onnx"
    if not model.exists():
        from piper.download_voices import download_voice
        print(f"Downloading voice {PIPER_VOICE} (one time)...", file=sys.stderr)
        model.parent.mkdir(parents=True, exist_ok=True)
        download_voice(PIPER_VOICE, model.parent)
    return PiperVoice.load(str(model))


class Voice:
    """Speaks text aloud.

    In order of preference:
      1. Fish Audio voice, when FISH_API_KEY is set (online, paid).
      2. Piper neural voice (free, offline, realistic male by default).
      3. The operating system's built-in voices via pyttsx3.
    """

    def __init__(self):
        self.engine = None
        self.fish = None
        self.piper = None
        if FISH_API_KEY:
            from fish_audio_sdk import Session
            self.fish = Session(FISH_API_KEY)
        try:
            self.piper = load_piper()
        except Exception as e:
            print(f"[Piper voice unavailable, using built-in voice: {e}]", file=sys.stderr)

    def _play(self, pcm, rate, channels=1, width=2):
        import sounddevice as sd
        dtype = {1: "uint8", 2: "int16", 4: "int32"}[width]
        with sd.RawOutputStream(samplerate=rate, channels=channels, dtype=dtype) as out:
            out.write(pcm)

    def _piper_say(self, text):
        chunks = list(self.piper.synthesize(text))   # one chunk per sentence
        pcm = b"".join(c.audio_int16_bytes for c in chunks)
        self._play(pcm, chunks[0].sample_rate)

    def _offline_engine(self):
        if self.engine is None:
            import pyttsx3
            self.engine = pyttsx3.init()
            self.engine.setProperty("rate", 175)     # words per minute
            self.engine.setProperty("volume", 1.0)
        return self.engine

    def _fish_say(self, text):
        import io, wave
        from fish_audio_sdk import TTSRequest
        req = TTSRequest(text=text, reference_id=FISH_VOICE_ID, format="wav")
        audio = b"".join(self.fish.tts(req, backend=FISH_MODEL))
        # Streamed WAVs can carry a placeholder length, so read the format from
        # the header but take the samples straight from after the "data" tag.
        with wave.open(io.BytesIO(audio)) as w:
            channels, width, rate = w.getnchannels(), w.getsampwidth(), w.getframerate()
        self._play(audio[audio.find(b"data") + 8:], rate, channels, width)

    def say(self, text):
        if self.fish:
            try:
                return self._fish_say(text)
            except Exception as e:
                print(f"[Fish Audio failed, using offline voice: {e}]", file=sys.stderr)
        if self.piper:
            try:
                return self._piper_say(text)
            except Exception as e:
                print(f"[Piper failed, using built-in voice: {e}]", file=sys.stderr)
        engine = self._offline_engine()
        engine.say(text)
        engine.runAndWait()


# --- Speech to text ----------------------------------------------------------

def _microphone():
    """A SpeechRecognition audio source backed by sounddevice, which pip installs
    with its own audio library on macOS and Windows (no Homebrew/PortAudio setup)."""
    import speech_recognition as sr
    import sounddevice as sd

    class Mic(sr.AudioSource):
        SAMPLE_RATE, SAMPLE_WIDTH, CHUNK = 16000, 2, 1024

        def __init__(self):
            self.stream = None

        def __enter__(self):
            self._input = sd.RawInputStream(samplerate=self.SAMPLE_RATE, channels=1,
                                            dtype="int16", blocksize=self.CHUNK)
            self._input.start()
            self.stream = self                    # SpeechRecognition calls stream.read()
            return self

        def read(self, frames):
            data, _overflowed = self._input.read(frames)
            return bytes(data)

        def __exit__(self, exc_type, exc_value, traceback):
            self._input.stop()
            self._input.close()
            self.stream = None

    return Mic()


class Ears:
    """Listens on the microphone and returns recognised text (or None)."""

    def __init__(self):
        import speech_recognition as sr
        self.sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 0.9     # silence that ends a phrase
        self.mic = _microphone()

        # Offline Vosk model present? Use it. Otherwise fall back to Google.
        self.vosk_model = None
        if os.path.isdir(VOSK_MODEL_DIR):
            try:
                from vosk import Model
                self.vosk_model = Model(VOSK_MODEL_DIR)
            except Exception:
                self.vosk_model = None

        with self.mic as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.6)

    def listen(self):
        with self.mic as source:
            audio = self.recognizer.listen(source, phrase_time_limit=15)
        try:
            if self.vosk_model is not None:
                import json
                from vosk import KaldiRecognizer
                rec = KaldiRecognizer(self.vosk_model, 16000)
                rec.AcceptWaveform(audio.get_wav_data(convert_rate=16000, convert_width=2))
                return json.loads(rec.FinalResult()).get("text", "").strip() or None
            return self.recognizer.recognize_google(audio).strip() or None
        except self.sr.UnknownValueError:
            return None                           # couldn't make out any words
        except self.sr.RequestError as e:
            print(f"[speech recognition unavailable: {e}]", file=sys.stderr)
            return None


# --- The brain ---------------------------------------------------------------

class Brain:
    """Holds the conversation and asks for replies from the first AI that works:
    Claude, Groq, Google Gemini (each if its key is set), then a local Ollama model."""

    def __init__(self):
        import urllib.request, urllib.error
        self.urllib = urllib
        self.history = [{"role": "system", "content": SYSTEM_PROMPT}]   # running memory
        if ANTHROPIC_API_KEY:
            import anthropic
            self.claude = anthropic.Anthropic()
        self.ollama_ok = self._ollama_ready()
        if not (ANTHROPIC_API_KEY or GROQ_API_KEY or GEMINI_API_KEY or self.ollama_ok):
            if not os.path.isfile(KEYS_FILE):
                hint = f"keys.txt was not found at {KEYS_FILE}"
            elif KEYS_LOADED:
                hint = f"keys.txt at {KEYS_FILE} has: {', '.join(KEYS_LOADED)} (but no AI key)"
            else:
                hint = f"keys.txt at {KEYS_FILE} has no AI key in it"
            sys.exit("No AI available. Install the free Ollama app from https://ollama.com and open it "
                     "(no account needed; Jarvis downloads its AI model by itself), "
                     "or put a GROQ_API_KEY or GEMINI_API_KEY in keys.txt.\n"
                     f"[{hint}]")

    def _ollama_ready(self):
        """True when Ollama is running with MODEL, downloading the model the first time."""
        request = self.urllib.request
        try:
            with request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=5) as r:
                models = [m["name"] for m in json.load(r).get("models", [])]
        except (OSError, ValueError):
            return False                        # Ollama not installed or not open
        if any(m == MODEL or m.split(":")[0] == MODEL for m in models):
            return True
        print(f"Downloading the AI model '{MODEL}' for Ollama (one time, about 2 GB)...", file=sys.stderr)
        req = request.Request(f"{OLLAMA_URL}/api/pull", data=json.dumps({"model": MODEL, "name": MODEL}).encode(),
                              headers={"Content-Type": "application/json"})
        shown = -10
        try:
            with request.urlopen(req, timeout=3600) as r:
                for line in r:              # one JSON progress message per line
                    msg = json.loads(line)
                    if msg.get("error"):
                        print(f"[Ollama download failed: {msg['error']}]", file=sys.stderr)
                        return False
                    if msg.get("total") and msg.get("completed"):
                        pct = int(msg["completed"] * 100 / msg["total"])
                        if pct >= shown + 10:
                            print(f"  {pct}%", file=sys.stderr)
                            shown = pct
        except (OSError, ValueError) as e:
            print(f"[Ollama download failed: {e}]", file=sys.stderr)
            return False
        print("AI model ready.", file=sys.stderr)
        return True

    def _post(self, url, payload, headers):
        # Groq sits behind Cloudflare, which blocks Python's default "Python-urllib"
        # identity with "403: error code: 1010", so name the app instead.
        req = self.urllib.request.Request(url, data=json.dumps(payload).encode(),
                                          headers={"Content-Type": "application/json",
                                                   "User-Agent": "jarvis-voice-assistant/1.0",
                                                   **headers})
        try:
            with self.urllib.request.urlopen(req, timeout=120) as r:
                return json.load(r)
        except self.urllib.error.HTTPError as e:
            raise RuntimeError(f"{e.code}: {e.read().decode(errors='replace')[:300]}") from None

    def _ask_claude(self):
        response = self.claude.beta.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=16000,
            system=SYSTEM_PROMPT,
            messages=self.history[1:],
            output_config={"effort": "low"},          # quick conversational replies
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",                      # retry on another model if declined
        )
        if response.stop_reason == "refusal":
            return "Sorry, I can't help with that one."
        return "".join(b.text for b in response.content if b.type == "text")

    def _ask_groq(self):
        try:
            import groq                         # official SDK (Python 3.10+): what Groq's firewall expects
        except ImportError:
            groq = None
        if groq is not None:
            if getattr(self, "groq", None) is None:
                self.groq = groq.Groq(api_key=GROQ_API_KEY,
                                      base_url=GROQ_URL.removesuffix("/openai/v1"))
            try:
                response = self.groq.chat.completions.create(model=GROQ_MODEL, messages=self.history)
            except groq.APIStatusError as e:
                raise RuntimeError(f"{e.status_code}: {e.message}") from None
            return response.choices[0].message.content
        data = self._post(f"{GROQ_URL}/chat/completions",
                          {"model": GROQ_MODEL, "messages": self.history},
                          {"Authorization": f"Bearer {GROQ_API_KEY}"})
        return data["choices"][0]["message"]["content"]

    def _ask_gemini(self):
        contents = [{"role": "model" if m["role"] == "assistant" else "user",
                     "parts": [{"text": m["content"]}]} for m in self.history[1:]]
        data = self._post(f"{GEMINI_URL}/models/{GEMINI_MODEL}:generateContent",
                          {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                           "contents": contents},
                          {"x-goog-api-key": GEMINI_API_KEY})
        return "".join(p.get("text", "") for p in data["candidates"][0]["content"]["parts"])

    def _ask_ollama(self):
        data = self._post(f"{OLLAMA_URL}/api/chat",
                          {"model": MODEL, "messages": self.history, "stream": False}, {})
        return data["message"]["content"]

    def reply(self, user_text):
        self.history.append({"role": "user", "content": user_text})
        # Try each AI you have a key for, in order. If one fails (e.g. Groq's firewall
        # blocking your network with "403 / 1010"), fall through to the next and stick with it.
        askers = [ask for key, ask in ((ANTHROPIC_API_KEY, self._ask_claude),
                                       (GROQ_API_KEY, self._ask_groq),
                                       (GEMINI_API_KEY, self._ask_gemini),
                                       (self.ollama_ok, self._ask_ollama)) if key]
        first = getattr(self, "working", 0)
        errors = []
        for n, ask in enumerate(askers[first:]):
            try:
                answer = ask().strip()
                self.working = first + n
                break
            except Exception as e:
                errors.append(f"{ask.__name__.removeprefix('_ask_').title()}: {e}")
        else:
            self.history.pop()          # keep the conversation consistent for the next try
            raise RuntimeError(" | ".join(errors))
        self.history.append({"role": "assistant", "content": answer})
        return answer


# --- Main loop ---------------------------------------------------------------

def main():
    # Status lines go to stderr so the *assistant's words* are never printed --
    # it truly only talks. These are just so you know what it's doing.
    def status(s):
        print(s, file=sys.stderr, flush=True)

    status("Starting up...")
    voice = Voice()
    brain = Brain()
    ears = Ears()

    voice.say("Hi, I'm your voice assistant. What can I do for you?")

    while True:
        status("Listening...")
        heard = ears.listen()
        if not heard:
            continue
        status(f"You: {heard}")

        if heard.lower().strip(".!? ") in EXIT_PHRASES:
            voice.say("Okay, goodbye!")
            break

        status("Thinking...")
        try:
            answer = brain.reply(heard)
        except Exception as e:
            status(f"[error: {e}]")
            voice.say("Sorry, something went wrong. Please try again.")
            continue

        status("Speaking...")
        voice.say(answer)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[stopped]", file=sys.stderr)
