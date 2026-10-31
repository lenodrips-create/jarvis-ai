#!/bin/bash
# Double-click to start Jarvis. It opens in your web browser; close this window to stop it.
cd "$(dirname "$0")"

PY=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python isn't installed. Get Python 3.12 from https://www.python.org/downloads/macos/"
  read -n 1 -s -r -p "Press any key to close."
  exit 1
fi

# First run: install what Jarvis needs.
if ! "$PY" -c "import piper, certifi, groq, fish_audio_sdk" >/dev/null 2>&1; then
  echo "Installing what Jarvis needs (one time)..."
  "$PY" -m pip install -r requirements.txt || { read -n 1 -s -r -p "Install failed. Press any key to close."; exit 1; }
fi

# Close any Jarvis still running from before: an old copy can be stuck or hold the microphone.
if pkill -f "jarvis_web.py" 2>/dev/null; then
  echo "Closing the Jarvis that was already running..."
  sleep 1
fi

"$PY" jarvis_web.py
