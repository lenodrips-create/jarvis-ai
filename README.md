# Jarvis for mac

welcome to JARVIS! the tony stark inspired ai that can do anything you program it to do.
---

## Contents

1. [Quick start](#quick-start)
2. [Talking with Jarvis: getting an AI key](#talking-with-jarvis-getting-an-ai-key)
3. [Changing Jarvis's voice](#changing-jarviss-voice)
4. [All settings (keys.txt)](#all-settings-keystxt)
5. [Troubleshooting](#troubleshooting)
6. [Privacy: what leaves your Mac](#privacy-what-leaves-your-mac)
7. [Ideas you could add](#ideas-you-could-add)

---

## Quick start/ how to set up. do exactly in this order

1. **Install Python 3.12** from <https://www.python.org/downloads/macos/> (3.10 and 3.11 also
   work; the newest Pythons don't yet). After installing, open **Applications → Python 3.12**
   and double-click **Install Certificates.command**.
2. **Double-click `Start Jarvis.command`** in this folder. The first time:
   - macOS may say it can't verify the developer: right-click the file, choose **Open**, then
     **Open** again.
     "this is found in the unzipped zip file"
   - It installs what Jarvis needs and downloads his voice (about 120 MB). This takes a few minutes.
3. **Jarvis opens in your browser** at <http://localhost:8765>. Use **Google Chrome** for the best
   speech recognition.
4. Click **Start Jarvis** and choose **Allow** for the microphone. He says *"Hello, I'm Jarvis."*
5. **Talk to him**, or type in the box at the bottom left and press Enter.

**To stop Jarvis**, close the small Terminal window that opened with him. Starting him again
closes any old copy automatically.

The top-right label shows his voice and version (for example `online · ryan · v31`).

-----

## Talking with Jarvis: getting an AI key

**Without a key, Jarvis only does the commands above.** Anything else gets
*"That's not one of my commands."*

**With a key, you can talk to him about anything**, and he still does all his commands.
You need only **one** key. If you add more than one, he uses the first in this order:
Claude, Groq, Gemini.

| Service | Cost | Where to get a key | Notes |
|---|---|---|---|
| **Claude** (Anthropic) | Paid, pay as you go | <https://console.anthropic.com> → **API Keys** → **Create Key** | Add some credit first. Uses Claude Opus 5.5; for cheaper, faster replies set `CLAUDE_MODEL=claude-haiku-5-5` |
| **Groq** | Free plan | <https://console.groq.com/keys> → **Create API Key** | Very fast. Some networks and countries are blocked by Groq |
| **Gemini** (Google) | Free plan | <https://aistudio.google.com/apikey> → **Create API key** | Needs a Google account that passes Google's age check |

**To add the key:**

1. Open `keys.txt` in this folder (it opens in TextEdit).
2. Paste the key right after the matching `=` sign, with no spaces. For example:
   ```
   GROQ_API_KEY=gsk_yourkeyhere
   ```
3. Save (**File → Save**) and restart Jarvis. The Terminal window should say `Talking: on`.

**Keep your keys private.** Never paste them into a chat, an email or a screenshot. If one
leaks, delete it on the service's website and make a new one.

**Free and offline alternative:** install the free **Ollama** app from <https://ollama.com>,
open it, and put `AI_ANSWERS=on` in `keys.txt`. Jarvis downloads a small AI model (about 2 GB)
the first time. Answers are simpler than the online services, but there's no key, no
account and no internet needed.

---

## Changing Jarvis's voice

### Free voices (Piper, run on your Mac)

Put one of these in `keys.txt`, save, and restart. A new voice downloads once (60–120 MB).

| Setting | Voice |
|---|---|
| `PIPER_VOICE=en_US-ryan-high` | Ryan, American man (default) |
| `PIPER_VOICE=en_GB-alan-medium` | Alan, British man (most "Jarvis") |
| `PIPER_VOICE=en_GB-northern_english_male-medium` | Northern English man |
| `PIPER_VOICE=en_US-joe-medium` | Joe, American man |
| `PIPER_VOICE=en_US-lessac-high` | American woman |
| `PIPER_VOICE=en_GB-cori-high` | British woman |

Listen to all of them at <https://rhasspy.github.io/piper-samples/>. Any voice name from
that page works.

### Your own voice from Fish Audio (paid)

1. Make or pick a voice at <https://fish.audio> and copy its **voice ID** (the long code).
2. Create an API key in your Fish Audio account's API section, and add credit if needed.
3. In `keys.txt`:
   ```
   FISH_API_KEY=your-key
   FISH_VOICE_ID=your-voice-id
   ```
4. Restart. The top-right label shows **fish audio**. If Fish Audio fails (no credit, no
   internet), Jarvis says that sentence in the Piper voice instead and the Terminal says why.

---

## All settings (keys.txt)

Each setting goes on its own line as `NAME=value`. Lines starting with `#` are notes.
Save and restart Jarvis after any change.

| Setting | What it does | Default |
add as you please. these are the defaults.
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude key: lets you talk with Jarvis | empty |
| `GROQ_API_KEY` | Groq key: lets you talk with Jarvis | empty |
| `GEMINI_API_KEY` | Gemini key: lets you talk with Jarvis | empty |
| `AI_ANSWERS` | `on` / `off` to force talking on or off (`on` with no key uses Ollama) | on with a key, otherwise off |
| `CLAUDE_MODEL` | Which Claude model | `claude-opus-5-5` |
| `GROQ_MODEL` | Which Groq model | `llama-3.3-70b-versatile` |
| `GEMINI_MODEL` | Which Gemini model | `gemini-flash-latest` |
| `OLLAMA_MODEL` | Which Ollama model (e.g. `qwen2.5:7b` if you have 16 GB+ memory) | `llama3.2` |
| `PIPER_VOICE` | Free voice (see above) | `en_US-ryan-high` |
| `FISH_API_KEY` | Fish Audio key for a custom voice | empty |
| `FISH_VOICE_ID` | Which Fish Audio voice | `612b878b113047d9a770c069c8b4fdfe` |
| `JARVIS_NAME` | Your name, used in "Good morning, …" and by the AI | none |
| `WEATHER_PLACE` | Town name Jarvis says in the weather | `anyloco` |
| `WEATHER_LAT` / `WEATHER_LON` | Your location for the weather (find yours at <https://www.latlong.net>) | 
| `NFL_TEAM` | Your team as ESPN's short code (`pit`, `kc`, `phi`, `dal`…) | `cin` (anyteam) |
| `GITHUB_USER` | Your GitHub username for "open hub" | empty |

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ResolutionImpossible` when installing | Use Python 3.12 (see Quick start), and start with `Start Jarvis.command` |
| `CERTIFICATE_VERIFY_FAILED` | Double-click **Install Certificates.command** in Applications → Python 3.12 |
| Jarvis doesn't hear you | Use Chrome; click the microphone icon in the address bar and choose **Allow** |
| Screen says "speaking" but no sound | Check the Mac's volume; right-click the tab and make sure it isn't muted |
| "That's not one of my commands" for everything | That's normal without an AI key: see [Talking with Jarvis](#talking-with-jarvis-getting-an-ai-key) |
| Key added but `Talking: off` | Make sure the key is right after the `=` with no spaces, the file is saved, and you restarted |
| `403 / error code 1010` | Groq is blocking your connection: try Claude or Gemini instead |
| Voice is Ryan, not your Fish Audio voice | Look in the Terminal for a line starting `[Fish Audio failed` for the reason |
| "Jarvis was opened in another tab" | Only one Jarvis tab works at a time; close the extra tabs |
| Running an old copy by mistake | The Terminal and top-right label show the version and folder; delete old `voice_assistant` folders |

---

## Privacy: what leaves your Mac

- **Stays on your Mac:** the Piper voice, Ollama, your Contacts, opening apps.
- **Goes to Google:** what you say, when the microphone is on (Chrome turns speech into text).
- **Goes to your AI service:** your questions, only if you added an AI key.
- **Goes to Fish Audio:** Jarvis's sentences, only if you added a Fish Audio key.
- **Looked up online when you ask:** weather (Open-Meteo), news (Fox News), sports (ESPN),
- ** this ai is localy hosted
---

## Ideas you could add

- A "hey Jarvis" wake word, so he only listens after his name
- Smart lights and plugs (Philips Hue, Apple Home)
- Timers, alarms and reminders
- Reading your calendar or emails
- Spotify control (play, pause, next song)
- Captions of what Jarvis says on screen
- A different orb colour or style
- Turning Jarvis into a normal Mac app you can double-click and share

---
