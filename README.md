# Sketchfab CLI Downloader

**Language / Язык:** **English** | [Русский](README.ru.md)

Download **public** 3D models from [Sketchfab](https://sketchfab.com) from the command line.

- **No** Sketchfab account  
- **No** API keys or tokens  
- Works even when the model has **no** Download button  
- Output: **glTF** (+ textures when available)  
- Windows / Linux / macOS  
- **Docker** — no need to install Python or Wine on the host  

> Console-only tool (no Telegram bot).

---

## Table of contents

1. [Features](#features)
2. [Requirements](#requirements)
3. [Quick start (Windows)](#quick-start-windows)
4. [Quick start (Linux)](#quick-start-linux)
5. [Quick start (macOS)](#quick-start-macos)
6. [Quick start (Docker)](#quick-start-docker) ← **recommended for beginners**
7. [How to use](#how-to-use)
8. [Where files are saved](#where-files-are-saved)
9. [CLI options](#cli-options)
10. [Examples](#examples)
11. [How it works](#how-it-works)
12. [FAQ / troubleshooting](#faq--troubleshooting)
13. [Project layout](#project-layout)
14. [Publishing to GitHub](#publishing-to-github)
15. [Legal disclaimer](#legal-disclaimer)
16. [License & credits](#license--credits)

---

## Features

| Feature | Description |
|---|---|
| Public model download | By full URL or 32-char hex UID |
| Models without Download | Uses the same mesh data the public 3D viewer loads |
| Multiple URLs | Pass several links in one run |
| Proxy | `--proxy http://host:port` |
| Output folder | `-o ./my_folder` |
| Textures | Public texture API when available |
| Conversion | glTF via `osgconv` (Windows tools) or Python fallback |
| Docker | Image with Python + Wine + tools; models land in `./downloads` |

**Not supported:**

- private / password-protected models  
- paid / exclusive downloads  
- logging into a Sketchfab account  

---

## Requirements

### Required

1. **Python 3.10+** (if not using Docker)  
   - Windows: https://www.python.org/downloads/  
   - Enable **“Add python.exe to PATH”** during install  
   - Check: `python --version` or `py -3 --version`

2. **Internet** — to download models (and the Docker image if you use containers).

### Easiest path — Docker

Install only [Docker](https://docs.docker.com/get-docker/) and follow  
[Quick start (Docker)](#quick-start-docker).  
The image already includes Python, Wine, and conversion tools.

### Recommended (local Python)

3. **Node.js 18+** — required for current Sketchfab `.binz` decryption (WASM)  
   - Windows/macOS: https://nodejs.org/  
   - Debian/Ubuntu: `sudo apt install nodejs`  
   - Check: `node --version`

4. **Conversion tools** (`tools/`, shipped in this repo)  
   - `tools/wasm/` — `decrypt_worker.mjs` + `decrypt.wasm` (auto-refreshed from viewer if missing)  
   - Static decrypt key is **fetched live** from Sketchfab viewer JS each run and cached in `tools/wasm/static_key.txt`  
   - `osgconv.exe` + DLLs — preferred glTF conversion (optional Python fallback)  
   - If tools are missing: `python setup_tools.py`

5. **Wine** — **Linux / macOS only**, for `osgconv.exe` (optional):

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install wine64

# Fedora
sudo dnf install wine
```

Wine is **not** required on Windows.  
Docker images already include Node.js + Wine + tools.

---

## Quick start (Windows)

### 1. Get the project

```bat
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli
```

Or **Code → Download ZIP** on GitHub and extract the folder.

### 2. Install Python dependencies

Open **cmd** or **PowerShell** in the project folder:

```bat
py -3 -m pip install -r requirements.txt
```

If `py` is not found:

```bat
python -m pip install -r requirements.txt
```

### 3. Check tools

The `tools\` folder should already exist. If not:

```bat
py -3 setup_tools.py
```

Verify:

```bat
py -3 main.py --check-tools
```

Expected files:

```text
tools\binz\binzDecrypt.exe
tools\OsgConv\osgconv.exe
```

### 4. Download a model

```bat
py -3 main.py https://sketchfab.com/3d-models/your-model-name-xxxxxxxx
```

Or interactive (the script asks for a URL):

```bat
py -3 main.py
```

Done — open the `downloads\` folder.

---

## Quick start (Linux)

```bash
# 1. Clone
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

# 2. Virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# 3. Dependencies
pip install -r requirements.txt

# 4. Node.js (required for decrypt) + optional Wine for osgconv
sudo apt update && sudo apt install -y nodejs wine64
python setup_tools.py   # only if tools/ is missing

# 5. Check and download
python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/..."
```

Models appear in `./downloads/`.

---

## Quick start (Docker)

Best if you do not want to install Python, pip, or Wine.  
You only need **Docker** (Docker Desktop on Windows/macOS, or `docker.io` + Compose on Linux).

### 1. Install Docker

- **Windows / macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)  
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update
  sudo apt install -y docker.io docker-compose-v2
  sudo systemctl enable --now docker
  # run docker without sudo (log out/in after):
  sudo usermod -aG docker "$USER"
  ```

Check:

```bash
docker --version
docker compose version
```

### 2. Clone and build the image

```bash
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

# First build may take several minutes (Python base image + Wine)
docker compose build
```

Or with plain Docker:

```bash
docker build -t sketchfab-cli:latest .
```

### 3. Download a model

**Option A — helper script:**

```bash
# Linux / macOS
chmod +x docker-download.sh
./docker-download.sh "https://sketchfab.com/3d-models/..."

# Windows (cmd / PowerShell)
docker-download.bat "https://sketchfab.com/3d-models/..."
```

**Option B — docker compose:**

```bash
# one model → files in ./downloads on your machine
docker compose run --rm downloader "https://sketchfab.com/3d-models/..."

# several
docker compose run --rm downloader URL1 URL2

# tools / Wine check inside the container
docker compose run --rm downloader --check-tools

# help
docker compose run --rm downloader --help

# proxy
docker compose run --rm downloader --proxy "http://host.docker.internal:7890" URL
```

**Option C — plain `docker run`:**

```bash
mkdir -p downloads

docker run --rm \
  -v "$PWD/downloads:/app/downloads" \
  sketchfab-cli:latest \
  "https://sketchfab.com/3d-models/..."
```

Windows (PowerShell):

```powershell
New-Item -ItemType Directory -Force downloads | Out-Null
docker run --rm `
  -v "${PWD}/downloads:/app/downloads" `
  sketchfab-cli:latest `
  "https://sketchfab.com/3d-models/..."
```

### 4. Where is the result?

On the **host** (not “stuck inside Docker”):

```text
sketchfab-cli/downloads/Model_Name-xxxxxxxx/
```

`./downloads` is mounted into the container as `/app/downloads`.

### Docker: useful commands

| Action | Command |
|---|---|
| Build / rebuild image | `docker compose build` |
| Download a model | `docker compose run --rm downloader URL` |
| Check tools | `docker compose run --rm downloader --check-tools` |
| Remove image | `docker rmi sketchfab-cli:latest` |

### Docker: no internet from the container

On some networks Docker’s bridge cannot reach HTTPS. Then:

1. Uncomment in `docker-compose.yml`:
   ```yaml
   network_mode: host
   ```
2. Run again:
   ```bash
   docker compose run --rm downloader URL
   ```

> `network_mode: host` behaves differently on **Docker Desktop (Windows/macOS)** than on Linux.  
> On Desktop, normal bridge + host VPN is often enough.

### Docker: disk & RAM

- Image size ~1–2 GB (Python + Wine + tools).  
- Prefer **≥ 2 GB RAM** for the first build (add swap on small VPS).  
- Downloaded models only use space under `./downloads` on the host.

---

## Quick start (macOS)

```bash
# Python: https://www.python.org/downloads/  or  brew install python
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Node.js required for decrypt
brew install node
# Optional Wine for osgconv.exe
brew install wine-stable
python setup_tools.py   # only if tools/ is missing

python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/..."
```

> On Apple Silicon, Wine may need extra setup.  
> If `osgconv` / `binzDecrypt` fail, the script may fall back to pure-Python glTF (quality can differ).

---

## How to use

### A — full URL

1. Open the model on sketchfab.com (must load **without login**).  
2. Copy the address bar URL, e.g.:

```text
https://sketchfab.com/3d-models/cool-robot-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

3. Run:

```bash
python main.py "https://sketchfab.com/3d-models/cool-robot-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
```

### B — UID only

UID is the 32 hex characters at the end of the URL:

```bash
python main.py a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

### C — several models

```bash
python main.py URL1 URL2 URL3
```

### D — interactive

```bash
python main.py
# > paste URL and press Enter
```

---

## Where files are saved

Default layout:

```text
sketchfab-cli/
└── downloads/
    └── Model_Name-abcd1234/
        ├── Model_Name.gltf      ← main file (open in Blender)
        ├── *.bin                ← mesh buffers next to glTF
        ├── textures/            ← textures if available
        └── info.json            ← name, author, source URL
```

**Blender:** `File → Import → glTF 2.0` → pick the `.gltf` file.

Custom folder:

```bash
python main.py -o ./my_models "https://sketchfab.com/3d-models/..."
```

---

## CLI options

```text
python main.py [OPTIONS] [URL_OR_UID ...]
```

| Option | Description |
|---|---|
| `URL_OR_UID` | One or more Sketchfab URLs or UIDs |
| `-o`, `--output DIR` | Output directory (default: `downloads/`) |
| `--proxy URL` | Proxy, e.g. `http://127.0.0.1:8080` |
| `--check-tools` | Verify tools / curl / wine and exit |
| `-q`, `--quiet` | Less banner text |
| `-h`, `--help` | Help |

---

## Examples

```bash
# One model
python main.py "https://sketchfab.com/3d-models/example-0123456789abcdef0123456789abcdef"

# Several
python main.py URL1 URL2

# Custom folder
python main.py -o ~/3d/sketchfab URL

# Proxy
python main.py --proxy "http://127.0.0.1:7890" URL

# Diagnostics only
python main.py --check-tools
```

### Windows: `download.bat`

```bat
download.bat "https://sketchfab.com/3d-models/..."
```

### Linux/macOS: `download.sh`

```bash
chmod +x download.sh
./download.sh "https://sketchfab.com/3d-models/..."
```

### Docker (short)

```bash
docker compose build
docker compose run --rm downloader "https://sketchfab.com/3d-models/..."
# or: ./docker-download.sh "URL"
```

See [Quick start (Docker)](#quick-start-docker).

---

## How it works

1. Opens the model’s **public** viewer page (like a browser).  
2. Reads JSON describing mesh files (`.binz`, etc.).  
3. Downloads those files from Sketchfab CDN.  
4. Decrypts `.binz` via **WASM** (Node.js) using:  
   - per-model key from public viewer JSON (`diter.b`)  
   - **static key auto-extracted** from live Sketchfab JS each run (cached under `tools/wasm/static_key.txt`)  
5. Converts to **glTF** (`osgconv` or built-in Python converter).  
6. Tries textures via public API `/i/models/{uid}/textures`.  
7. Writes everything under `downloads/` plus `info.json`.

```text
URL → viewer JSON → download .binz → decrypt → glTF + textures → downloads/
```

---

## FAQ / troubleshooting

### `python` / `py` not found

- Reinstall Python with **Add to PATH** enabled.  
- Or use the full path, e.g.:
  ```bat
  C:\Users\YOU\AppData\Local\Programs\Python\Python312\python.exe main.py --help
  ```

### `WARNING: missing ... binzDecrypt.exe`

1. Clone the **full** repository (`tools/` must not be empty).  
2. Or run:
   ```bash
   python setup_tools.py
   ```
3. If mirrors fail, copy `tools/binz` and `tools/OsgConv` from a complete project archive.

### `Cannot run binzDecrypt.exe: wine not found` (Linux)

Local Python:

```bash
sudo apt install wine64
python main.py --check-tools
```

Or use **Docker** (Wine is already in the image) — see [Quick start (Docker)](#quick-start-docker).

### Docker: `permission denied` / `Cannot connect to the Docker daemon`

- Is Docker running? (`sudo systemctl start docker` or Docker Desktop).  
- On Linux, add your user to the `docker` group and **re-login**:
  ```bash
  sudo usermod -aG docker "$USER"
  ```
- Or use `sudo docker compose ...` temporarily.

### Docker: `network is unreachable` / timeout to sketchfab.com

- Test the host: `curl -I https://sketchfab.com`  
- Try `network_mode: host` in `docker-compose.yml` (Linux).  
- Corporate VPN/proxy: pass `--proxy` to `downloader`.

### SSL / network failures

- Check internet.  
- Antivirus HTTPS scanning may break TLS — try disabling it briefly.  
- Confirm `pip install -r requirements.txt` succeeded.

### Model “does not download”

1. Open the same link in a **private/incognito** window without login. If it fails, the model is not public.  
2. Paid / exclusive models are not supported.  
3. Sketchfab may have changed formats — delete `tools/binz` and `tools/OsgConv`, run `python setup_tools.py` again (or re-clone).

### Slow decrypt / convert

- First Wine start on Linux initializes a prefix (1–2 minutes is normal).  
- Large models take longer to download.

### Use as a library

```python
from main import download_one

info = download_one("https://sketchfab.com/3d-models/...")
print(info["path"], info["name"], info["author"])
```

---

## Project layout

```text
sketchfab-cli/
├── main.py                 # CLI + download logic
├── osgjs_convert.py        # Python fallback osgjs → glTF
├── textures.py             # Texture download
├── setup_tools.py          # Verify / re-fetch tools
├── requirements.txt        # Python dependencies
├── Dockerfile              # Image: Python + Wine + tools
├── docker-compose.yml      # compose run downloader URL
├── .dockerignore
├── docker-download.sh      # Docker helper (Linux/macOS)
├── docker-download.bat     # Docker helper (Windows)
├── download.bat            # Local run on Windows (no Docker)
├── download.sh             # Local run on Linux/macOS
├── downloads/              # Output (not committed)
├── tools/
│   ├── wasm/               # decrypt_worker.mjs + decrypt.wasm (+ cached static_key.txt)
│   ├── binz/               # legacy binzDecrypt.exe (optional fallback)
│   └── OsgConv/            # osgconv.exe + DLLs
├── LICENSE
├── README.md               # English docs (default on GitHub)
└── README.ru.md            # Russian docs
```

---

## Publishing to GitHub

```bash
cd sketchfab-cli
git init
git add .
git status   # downloads/ should not appear; tools/ should
git commit -m "Initial commit: Sketchfab CLI downloader"
git branch -M main
git remote add origin https://github.com/seryi882/sketchfab-cli.git
git push -u origin main
```

- **Do not commit** `downloads/` (user models) — listed in `.gitignore`.  
- **Do commit** `tools/` (~40 MB): without it, decryption fails for new users.  
- GitHub hard limit is 100 MB per file; `binzDecrypt.exe` is ~18 MB.

### PR ideas

- better Python converter  
- tests / CI  
- docs improvements  

---

## Legal disclaimer

This tool is for **personal** access to **publicly** available viewer data, the same way a browser does.

- Follow [Sketchfab Terms of Use](https://sketchfab.com/terms).  
- Respect author licenses (CC, Editorial, etc.) shown on the model page.  
- Do not use for mass piracy, resale, or bypassing paid downloads.  
- Authors are **not liable** for how you use the software.

---

## License & credits

- CLI code: **MIT** (see `LICENSE`).  
- `binzDecrypt` / `osgconv` tools originate from community Sketchfab-Ripper tooling  
  and remain under their respective authors’ terms.  
- Sketchfab is a trademark of its owners.

---

### Cheat sheet

**Docker (no host Python):**

```bash
docker compose build
docker compose run --rm downloader "https://sketchfab.com/3d-models/....."
# → see downloads/
```

**Local Python:**

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Need Node.js 18+ (decrypt). Linux optional Wine for osgconv:
#   sudo apt install nodejs wine64
python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/....."
# → see downloads/
```

### Auto-updating keys

You normally **do not** need to edit keys by hand:

| Material | Source | Updates how? |
|---|---|---|
| Per-model `diter.b` | Public model embed JSON | Always live |
| Static 40-hex key | Viewer JS on static.sketchfab.com | Extracted every download; saved to `tools/wasm/static_key.txt` |
| `decrypt.wasm` | Embedded in viewer JS | Shipped in repo; re-extracted if missing / on decrypt failure |

If Sketchfab rotates crypto and a download fails, pull the latest release or re-run the same command once (wasm/key refresh is attempted automatically).

If something fails, start with `python main.py --check-tools` (or Docker equivalent) and the [FAQ](#faq--troubleshooting).
