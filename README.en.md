# Fitz 1.2.0.0

🌐 [Русский](README.md) · English

Fitz is a desktop AI assistant built with PyQt6, with an animated Live2D character (Haru). It understands text commands, answers through a language-model API, controls Linux systems, keeps memory, can look at the screen and open applications.

> Version 1.2.0.0 is verified by unit tests and command calls. A full manual GUI run (voice, Live2D, chat window) was **not** performed for this version — see "Not verified".

---

## Contents

- [Features](#features)
- [What works and what doesn't](#what-works-and-what-doesnt)
- [Installation](#installation)
- [Connecting the API](#connecting-the-api)
- [Running](#running)
- [Commands](#commands)
- [Project structure](#project-structure)
- [Tests](#tests)
- [Troubleshooting](#troubleshooting)
- [Known issues](#known-issues)
- [Changes in 1.2.0.0](#changes-in-1200)

---

## Features

- **Conversation and time:** greetings, time, date, jokes, help.
- **System (Linux, GNOME):** system status (CPU, RAM), screen lock, volume, opening applications.
- **Reminders:** "напомни через 5 минут …" (the phrase is Russian; see commands).
- **Network:** weather, your external IP address, link checks.
- **Chat history search:** "найди в истории <word>".
- **Memory and knowledge:** stored in `data/brain.json` and `data/intelligence.db`.
- **Haru character:** Live2D model in a window, reacts to speech (lip-sync).
- **Settings:** theme, opacity, character size, API connection — in the settings window.

## What works and what doesn't

| Feature | Status | Notes |
|---|---|---|
| Time, date, help, jokes | ✅ Verified by calling commands | |
| System status (CPU, RAM, API key presence, `data/` size, DLC count) | ✅ Verified | The key is shown only as "set / not set" |
| Chat history search | ✅ Verified | |
| Reminders | ✅ Verified | |
| Weather, IP, opening applications | ✅ Verified by calling commands | Depends on network and installed apps |
| Screen lock, volume | ✅ Verified by calling commands | Linux: `loginctl`, `wpctl`/`pactl` |
| Answers via a language-model API | ⚠️ Not verified | Needs a key; see [Connecting the API](#connecting-the-api) |
| Voice (recognition and speech) | ⚠️ Not verified manually | Needs a microphone and dependencies |
| Haru character (Live2D) and lip-sync | ⚠️ Not verified manually | |
| Streaming answers | ❌ Not implemented | Planned |
| Closing windows by name on Linux | ❌ Does not work on Wayland | Needs a GNOME extension and re-login |
| Confirmation before closing several windows | ❌ Not implemented | |
| "Diary", "remember …", "what do you know" | ❌ Not working | See [Known issues](#known-issues) |
| Anti-theft | ❌ Removed | It never detected intrusions |

## Installation

Requires Python 3.12. Verified on Linux (GNOME, Wayland).

```bash
git clone git@github.com:sima-lang/Fitz-1.1.5.0.git
cd Fitz-1.1.5.0
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock
```

`requirements.lock` pins the exact versions the release was verified with. `requirements-windows.txt` exists for Windows but was not verified in this version.

Optional for voice and vision: system packages (for example `portaudio` for `sounddevice`, `tesseract` for OCR). Without them, those features are disabled and the rest keeps working.

## Connecting the API

Fitz works without an API, but conversation with a language model needs a key. There are two ways; they can be combined.

### Option 1 — settings window (recommended)

1. Start Fitz and open **Settings**.
2. Go to the **🔌 API** tab.
3. Fill in the fields:
   - **API Key** — your key (the field hides it as dots).
   - **API URL** — service address. Default: `https://api.provod.ai/v1`.
   - **Model** — pick from the list or type your own. Available: `deepseek/deepseek-v4.1-flash`, `deepseek/deepseek-v4-pro`, `deepseek/deepseek-v4-flash`, `grok-4-flash`.
   - **Timeout** — 30 to 300 seconds.
4. Press the API check button and save.
5. Turn "Check API on start" on or off.

Settings are saved to `data/settings.json`. The key from this file is picked up at startup if `.env` does not set one.

### Option 2 — `.env` file

Create a `.env` file in the project root (it is not committed to git):

```ini
API_KEY=your_key
API_URL=https://api.provod.ai/v1
API_MODEL=deepseek/deepseek-v4-flash
API_TIMEOUT=60
```

A value in `.env` takes precedence over the settings window.

### Checking it

The command "состояние" (status) shows whether a key is set: "API-ключ: задан" or "не задан". The key value itself is never printed.

> ⚠️ Do not publish your key. `.env` and `data/` are in `.gitignore`, but check before every commit.

## Running

```bash
source .venv/bin/activate
python3 ui_pyqt.py
```

Logs go to `data/fitz.log` (general), `data/voice.log`, `data/brain.log`, `data/ui.log` — per module.

Building an executable: `build.py` / `build_exe.py` (PyInstaller) and `build_deb.sh`. Not verified on a clean system in this version.

## Commands

Example phrases. Case does not matter. Most phrases are in Russian, as the assistant is Russian-speaking.

| Say | What happens |
|---|---|
| привет | Greeting |
| время / который час | Current time |
| дата | Today's date |
| состояние / мониторинг | CPU, RAM, API key presence, `data/` size, DLC count |
| найди в истории погода | Searches `data/chat_history.json` |
| напомни через 5 минут проверить чай | Reminder |
| шутка | Random joke |
| погода | Weather for the default city |
| мой ip | External IP |
| открой калькулятор | Opens an application |
| блокировка | Locks the screen |
| громче / тише | Volume |
| камера | Camera status |
| помощь | List of commands |

## Project structure

| Path | Purpose |
|---|---|
| `ui_pyqt.py` | Entry point, main window |
| `ui/` | Windows: chat, settings, Haru, logs, loading |
| `commands/` | Command handlers (system, files, network, security) |
| `core/` | Core: API, memory, voice, logging, utilities |
| `life/` | Character, autosave, initiative |
| `vision/` | Camera and screenshots |
| `security/` | Link checks (`safe_links.py`) |
| `data/` | User data: memory, history, settings (not in git) |
| `live2d/`, `assets/` | Haru model and resources |
| `test_fitz.py`, `test_scenarios.py` | Tests |
| `backup_before_audit/` | Backups made before edits (not in git) |

## Tests

```bash
pip install pytest ruff
QT_QPA_PLATFORM=offscreen python3 -m pytest test_fitz.py test_scenarios.py -q
ruff check --select F401,F811,F821,F841 $(git ls-files '*.py' | grep -v Fitz.AppDir)
```

Result for version 1.2.0.0: 112 passed, 2 skipped. The linter with these rules is clean. The full `ruff check` shows style findings (mostly broad `except` clauses), not errors.

## Troubleshooting

**Fitz says "API key is not set".**
Open Settings → API and enter the key, or add `API_KEY` to `.env`. Check with the "состояние" command.

**Weather or IP does not work.**
A network connection is required. Check your internet and `data/fitz.log` for `requests` errors.

**A window cannot be closed by name.**
On Wayland this needs the GNOME extension `fitz-close@local` and a re-login. Close the window manually.

**`psutil не установлен` error.**
Run `pip install psutil` in the active environment.

**No sound or voice.**
Check the microphone and the system packages for `sounddevice`. Without them voice is disabled; the text chat still works.

**Haru window does not appear or is blank.**
Check that a model is present in `live2d/` and that Haru is enabled in settings. See `data/ui.log`.

**Settings are not saved.**
Check write permissions for `data/`. Writes are atomic: on error the old file is kept.

**Something broke after an update.**
Backups of edits are in `backup_before_audit/`. You can roll back with `git log` and `git checkout <commit> -- <file>`.

If your problem is not listed, check `data/fitz.log` and `data/ui.log` and include them in your report.

## Known issues

- The "дневник" (diary) command replies "нет модуля intelligence", although `core/intelligence.py` exists. This is a router bug.
- The phrases "запомни что у меня кот" and "что ты знаешь" are not recognized.
- Link checking (`security/safe_links.py`): between the address check and the request, DNS may return a different address (DNS rebinding). Full protection is not implemented.
- Language-model answers in 1.2.0.0 were tested only with unit tests that mock the API.

## Changes in 1.2.0.0

**Added**
- System status command (CPU, RAM, API key without its value, `data/` size, DLC).
- Chat history search.
- Separate logs per module.
- `requirements.lock` with exact versions.

**Fixed**
- SSRF via redirects in link checking: each step is checked before the request.
- All host addresses are checked, including IPv6.
- File deletion in `super_vision` is limited to portal screenshots.
- Atomic JSON writes (settings, profile, memory, chat history).
- The key from the settings window is applied at startup.
- Log messages describe the action instead of a misleading phrase.
- Image hash uses sha256 instead of md5; `mss.MSS` instead of the deprecated `mss.mss`.

**Removed**
- `security/anti_theft.py` — it never detected intrusions.
- The DLC module "greed" and its references.

**Access limits**
- File commands work only in Desktop, Documents, Downloads, Pictures and the project folder. Files directly in the home folder and `~/.ssh`, `~/.gnupg` are not accessible.

**Not done**
- `CHANGELOG.md`, streaming answers, confirmation before closing several windows, an import smoke test in CI, a manual GUI run.
