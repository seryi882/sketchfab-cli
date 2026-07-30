# Sketchfab CLI Downloader

**Language / Язык:** [English](README.md) | **Русский**

Скачивание **публичных** 3D-моделей с [Sketchfab](https://sketchfab.com) через командную строку.

- **Без** аккаунта Sketchfab  
- **Без** API-ключей и токенов  
- Работает даже если у модели **нет** кнопки Download  
- Результат: **glTF** (+ текстуры, когда доступны)  
- Windows / Linux / macOS  
- **Docker** — можно без установки Python и Wine на хосте  

> Консольная версия (без Telegram-бота).

---

## Оглавление

1. [Возможности](#возможности)
2. [Требования](#требования)
3. [Быстрый старт (Windows)](#быстрый-старт-windows)
4. [Быстрый старт (Linux)](#быстрый-старт-linux)
5. [Быстрый старт (macOS)](#быстрый-старт-macos)
6. [Быстрый старт (Docker)](#быстрый-старт-docker) ← **рекомендуется новичкам**
7. [Как пользоваться](#как-пользоваться)
8. [Куда сохраняются файлы](#куда-сохраняются-файлы)
9. [Параметры командной строки](#параметры-командной-строки)
10. [Примеры](#примеры)
11. [Как это работает](#как-это-работает)
12. [Частые вопросы и ошибки](#частые-вопросы-и-ошибки)
13. [Структура проекта](#структура-проекта)
14. [Публикация на GitHub](#публикация-на-github)
15. [Правовой дисклеймер](#правовой-дисклеймер)
16. [Лицензия и благодарности](#лицензия-и-благодарности)

---

## Возможности

| Возможность | Описание |
|---|---|
| Скачать публичную модель | По полной ссылке или 32-символьному hex UID |
| Модели без Download | Берёт mesh из данных публичного 3D-viewer |
| Несколько ссылок | Можно передать несколько URL за один запуск |
| Прокси | `--proxy http://host:port` |
| Папка вывода | `-o ./my_folder` |
| Текстуры | Публичный texture API, если доступен |
| Конвертация | glTF через `osgconv` (Windows-tools) или Python-fallback |
| Docker | Образ с Python + Wine + tools; модели в `./downloads` |

**Не поддерживается:**

- приватные / password-protected модели  
- платные / exclusive download  
- вход в аккаунт Sketchfab  

---

## Требования

### Обязательно

1. **Python 3.10+** (если не используете Docker)  
   - Windows: https://www.python.org/downloads/  
   - При установке включите **“Add python.exe to PATH”**  
   - Проверка: `python --version` или `py -3 --version`

2. **Интернет** — чтобы скачивать модели (и Docker-образ, если работаете через контейнер).

### Самый простой путь — Docker

Установите только [Docker](https://docs.docker.com/get-docker/) и следуйте  
разделу [Быстрый старт (Docker)](#быстрый-старт-docker).  
В образе уже есть Python, Wine и tools.

### Рекомендуется (локальный Python)

3. **Node.js 18+** — нужен для расшифровки `.binz` (WASM)  
   - Windows/macOS: https://nodejs.org/  
   - Debian/Ubuntu: `sudo apt install nodejs`  
   - Проверка: `node --version`

4. **Инструменты** (`tools/`, уже в репозитории)  
   - `tools/wasm/` — `decrypt_worker.mjs` + `decrypt.wasm` (докачивается из viewer, если нет)  
   - Static-ключ **каждый запуск берётся из live JS** Sketchfab и кэшируется в `tools/wasm/static_key.txt`  
   - `osgconv.exe` + DLL — конвертация в glTF (опционально, есть Python-fallback)  
   - Если tools нет: `python setup_tools.py`

5. **Wine** — **только Linux / macOS**, для `osgconv.exe` (опционально):

```bash
# Debian / Ubuntu
sudo apt update
sudo apt install wine64

# Fedora
sudo dnf install wine
```

На Windows Wine **не нужен**.

---

## Быстрый старт (Windows)

### 1. Скачайте проект

```bat
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli
```

Или **Code → Download ZIP** на GitHub и распакуйте папку.

### 2. Установите зависимости Python

Откройте **cmd** или **PowerShell** в папке проекта:

```bat
py -3 -m pip install -r requirements.txt
```

Если `py` не находится:

```bat
python -m pip install -r requirements.txt
```

### 3. Проверьте tools

Папка `tools\` уже должна быть. Если нет:

```bat
py -3 setup_tools.py
```

Проверка:

```bat
py -3 main.py --check-tools
```

Ожидаемые файлы:

```text
tools\binz\binzDecrypt.exe
tools\OsgConv\osgconv.exe
```

### 4. Скачайте модель

```bat
py -3 main.py https://sketchfab.com/3d-models/your-model-name-xxxxxxxx
```

Или интерактивно (скрипт спросит ссылку):

```bat
py -3 main.py
```

Готово — смотрите папку `downloads\`.

---

## Быстрый старт (Linux)

```bash
# 1. Клонировать
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

# 2. Виртуальное окружение (рекомендуется)
python3 -m venv .venv
source .venv/bin/activate

# 3. Зависимости
pip install -r requirements.txt

# 4. Node.js (обязателен) + опционально Wine для osgconv
sudo apt update && sudo apt install -y nodejs wine64
python setup_tools.py   # только если tools/ отсутствует

# 5. Проверка и скачивание
python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/..."
```

Модели появятся в `./downloads/`.

---

## Быстрый старт (Docker)

Удобно, если не хотите ставить Python, pip и Wine.  
Нужен только **Docker** (Docker Desktop на Windows/macOS или `docker.io` + Compose на Linux).

### 1. Установите Docker

- **Windows / macOS:** [Docker Desktop](https://www.docker.com/products/docker-desktop/)  
- **Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update
  sudo apt install -y docker.io docker-compose-v2
  sudo systemctl enable --now docker
  # docker без sudo (после команды выйдите из сессии и зайдите снова):
  sudo usermod -aG docker "$USER"
  ```

Проверка:

```bash
docker --version
docker compose version
```

### 2. Клонируйте проект и соберите образ

```bash
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

# Первая сборка может занять несколько минут (образ Python + Wine)
docker compose build
```

Или обычным Docker:

```bash
docker build -t sketchfab-cli:latest .
```

### 3. Скачайте модель

**Вариант A — helper-скрипт:**

```bash
# Linux / macOS
chmod +x docker-download.sh
./docker-download.sh "https://sketchfab.com/3d-models/..."

# Windows (cmd / PowerShell)
docker-download.bat "https://sketchfab.com/3d-models/..."
```

**Вариант B — docker compose:**

```bash
# одна модель → файлы в ./downloads на вашем компьютере
docker compose run --rm downloader "https://sketchfab.com/3d-models/..."

# несколько
docker compose run --rm downloader URL1 URL2

# проверка tools / Wine внутри контейнера
docker compose run --rm downloader --check-tools

# справка
docker compose run --rm downloader --help

# прокси
docker compose run --rm downloader --proxy "http://host.docker.internal:7890" URL
```

**Вариант C — «голый» `docker run`:**

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

### 4. Где результат?

На **хосте** (не «внутри Docker»):

```text
sketchfab-cli/downloads/Model_Name-xxxxxxxx/
```

Папка `./downloads` смонтирована в контейнер как `/app/downloads`.

### Docker: полезные команды

| Действие | Команда |
|---|---|
| Собрать / пересобрать образ | `docker compose build` |
| Скачать модель | `docker compose run --rm downloader URL` |
| Проверить tools | `docker compose run --rm downloader --check-tools` |
| Удалить образ | `docker rmi sketchfab-cli:latest` |

### Docker: нет интернета из контейнера

На некоторых сетях bridge Docker не пускает HTTPS наружу. Тогда:

1. В `docker-compose.yml` раскомментируйте:
   ```yaml
   network_mode: host
   ```
2. Запустите снова:
   ```bash
   docker compose run --rm downloader URL
   ```

> `network_mode: host` на **Docker Desktop (Windows/macOS)** работает иначе, чем на Linux.  
> На Desktop обычно хватает обычного bridge + VPN на хосте.

### Docker: место на диске и RAM

- Размер образа ~1–2 GB (Python + Wine + tools).  
- Для первой сборки желательно **≥ 2 GB RAM** (на слабых VPS добавьте swap).  
- Скачанные модели занимают место только в `./downloads` на хосте.

---

## Быстрый старт (macOS)

```bash
# Python: https://www.python.org/downloads/  или  brew install python
git clone https://github.com/seryi882/sketchfab-cli.git
cd sketchfab-cli

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Wine (Homebrew) — tools/ уже в репозитории
brew install wine-stable
# или: brew install --cask wine-stable
python setup_tools.py   # только если tools/ отсутствует

python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/..."
```

> На Apple Silicon Wine может потребовать дополнительной настройки.  
> Если `osgconv` / `binzDecrypt` не работают, скрипт может перейти на pure-Python glTF (качество может отличаться).

---

## Как пользоваться

### A — полная ссылка

1. Откройте модель на sketchfab.com (должна открываться **без логина**).  
2. Скопируйте URL из адресной строки, например:

```text
https://sketchfab.com/3d-models/cool-robot-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

3. Запустите:

```bash
python main.py "https://sketchfab.com/3d-models/cool-robot-a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
```

### B — только UID

UID — 32 hex-символа в конце ссылки:

```bash
python main.py a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
```

### C — несколько моделей

```bash
python main.py URL1 URL2 URL3
```

### D — интерактивно

```bash
python main.py
# > вставьте URL и нажмите Enter
```

---

## Куда сохраняются файлы

Структура по умолчанию:

```text
sketchfab-cli/
└── downloads/
    └── Model_Name-abcd1234/
        ├── Model_Name.gltf      ← основной файл (откройте в Blender)
        ├── *.bin                ← буферы mesh рядом с glTF
        ├── textures/            ← текстуры, если удалось скачать
        └── info.json            ← имя, автор, исходная ссылка
```

**Blender:** `File → Import → glTF 2.0` → выберите `.gltf`.

Своя папка:

```bash
python main.py -o ./my_models "https://sketchfab.com/3d-models/..."
```

---

## Параметры командной строки

```text
python main.py [OPTIONS] [URL_OR_UID ...]
```

| Параметр | Описание |
|---|---|
| `URL_OR_UID` | Одна или несколько ссылок Sketchfab / UID |
| `-o`, `--output DIR` | Папка вывода (по умолчанию `downloads/`) |
| `--proxy URL` | Прокси, например `http://127.0.0.1:8080` |
| `--check-tools` | Проверить tools / curl / wine и выйти |
| `-q`, `--quiet` | Меньше служебного текста |
| `-h`, `--help` | Справка |

---

## Примеры

```bash
# Одна модель
python main.py "https://sketchfab.com/3d-models/example-0123456789abcdef0123456789abcdef"

# Несколько
python main.py URL1 URL2

# Своя папка
python main.py -o ~/3d/sketchfab URL

# Прокси
python main.py --proxy "http://127.0.0.1:7890" URL

# Только диагностика
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

### Docker (кратко)

```bash
docker compose build
docker compose run --rm downloader "https://sketchfab.com/3d-models/..."
# или: ./docker-download.sh "URL"
```

Подробнее: [Быстрый старт (Docker)](#быстрый-старт-docker).

---

## Как это работает

1. Открывает **публичную** страницу viewer модели (как браузер).  
2. Читает JSON с описанием mesh-файлов (`.binz` и т.д.).  
3. Скачивает их с CDN Sketchfab.  
4. Расшифровывает `.binz` через **WASM** (Node.js):  
   - per-model ключ из публичного JSON (`diter.b`)  
   - **static key** автоматически из live JS Sketchfab (кэш: `tools/wasm/static_key.txt`)  
5. Конвертирует в **glTF** (`osgconv` или встроенный Python-конвертер).  
6. Пытается скачать текстуры через API `/i/models/{uid}/textures`.  
7. Кладёт всё в `downloads/` и пишет `info.json`.

```text
URL → viewer JSON → download .binz → decrypt → glTF + textures → downloads/
```

---

## Частые вопросы и ошибки

### `python` / `py` не найден

- Переустановите Python с галочкой **Add to PATH**.  
- Или укажите полный путь, например:
  ```bat
  C:\Users\YOU\AppData\Local\Programs\Python\Python312\python.exe main.py --help
  ```

### `WARNING: missing ... binzDecrypt.exe`

1. Клонируйте **полный** репозиторий (папка `tools/` не должна быть пустой).  
2. Или:
   ```bash
   python setup_tools.py
   ```
3. Если зеркала недоступны — скопируйте `tools/binz` и `tools/OsgConv` из полного архива проекта.

### `Cannot run binzDecrypt.exe: wine not found` (Linux)

Локальный Python:

```bash
sudo apt install wine64
python main.py --check-tools
```

Или **Docker** (Wine уже в образе) — см. [Быстрый старт (Docker)](#быстрый-старт-docker).

### Docker: `permission denied` / `Cannot connect to the Docker daemon`

- Запущен ли Docker? (`sudo systemctl start docker` или Docker Desktop).  
- На Linux добавьте пользователя в группу `docker` и **перелогиньтесь**:
  ```bash
  sudo usermod -aG docker "$USER"
  ```
- Временно: `sudo docker compose ...`

### Docker: `network is unreachable` / timeout к sketchfab.com

- Проверьте хост: `curl -I https://sketchfab.com`  
- Попробуйте `network_mode: host` в `docker-compose.yml` (Linux).  
- Корпоративный VPN/прокси: передайте `--proxy` в `downloader`.

### SSL / сетевые ошибки

- Проверьте интернет.  
- HTTPS-сканирование антивируса может ломать TLS — временно отключите.  
- Убедитесь, что `pip install -r requirements.txt` прошёл успешно.

### Модель «не скачивается»

1. Откройте ту же ссылку в **инкогнито** без логина. Если не открывается — модель не публичная.  
2. Платные / exclusive модели не поддерживаются.  
3. Формат мог измениться — удалите `tools/binz` и `tools/OsgConv`, снова `python setup_tools.py` (или переклонируйте).

### Долго decrypt / convert

- Первый запуск Wine на Linux инициализирует prefix (1–2 минуты — нормально).  
- Большие модели качаются дольше.

### Использование как библиотеки

```python
from main import download_one

info = download_one("https://sketchfab.com/3d-models/...")
print(info["path"], info["name"], info["author"])
```

---

## Структура проекта

```text
sketchfab-cli/
├── main.py                 # CLI + логика скачивания
├── osgjs_convert.py        # Python fallback osgjs → glTF
├── textures.py             # Скачивание текстур
├── setup_tools.py          # Проверка / докачка tools
├── requirements.txt        # Зависимости Python
├── Dockerfile              # Образ: Python + Wine + tools
├── docker-compose.yml      # compose run downloader URL
├── .dockerignore
├── docker-download.sh      # Docker helper (Linux/macOS)
├── docker-download.bat     # Docker helper (Windows)
├── download.bat            # Локальный запуск на Windows
├── download.sh             # Локальный запуск на Linux/macOS
├── downloads/              # Результаты (не в git)
├── tools/                  # binzDecrypt + osgconv (в репозитории)
├── LICENSE
├── README.md               # English docs
└── README.ru.md            # Русская документация (этот файл)
```

---

## Публикация на GitHub

```bash
cd sketchfab-cli
git init
git add .
git status   # downloads/ не должен попасть; tools/ — должен
git commit -m "Initial commit: Sketchfab CLI downloader"
git branch -M main
git remote add origin https://github.com/seryi882/sketchfab-cli.git
git push -u origin main
```

- **Не коммитьте** `downloads/` (модели пользователя) — в `.gitignore`.  
- **Коммитьте** `tools/` (~40 MB): без них у новичков не сработает decrypt.  
- Лимит GitHub: 100 MB на файл; `binzDecrypt.exe` ≈ 18 MB.

### Идеи для PR

- улучшение Python-конвертера  
- тесты / CI  
- доработка документации  

---

## Правовой дисклеймер

Инструмент предназначен для **личного** доступа к **публично** доступным данным viewer, как это делает браузер.

- Соблюдайте [Terms of Use Sketchfab](https://sketchfab.com/terms).  
- Уважайте лицензии авторов (CC, Editorial и т.д.) на странице модели.  
- Не используйте для массового пиратства, перепродажи или обхода платного download.  
- Авторы **не несут ответственности** за использование ПО.

---

## Лицензия и благодарности

- Код CLI: **MIT** (см. `LICENSE`).  
- Инструменты `binzDecrypt` / `osgconv` происходят из community Sketchfab-Ripper tooling  
  и остаются на условиях своих авторов.  
- Sketchfab — торговая марка правообладателей.

---

### Шпаргалка

**Docker (без Python на хосте):**

```bash
docker compose build
docker compose run --rm downloader "https://sketchfab.com/3d-models/....."
# → смотрите downloads/
```

**Локальный Python:**

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
# Нужен Node.js 18+. Linux: sudo apt install nodejs wine64
python main.py --check-tools
python main.py "https://sketchfab.com/3d-models/....."
# → смотрите downloads/
```

### Автообновление ключей

Вручную править ключи **не нужно**:

| Материал | Откуда | Как обновляется |
|---|---|---|
| Per-model `diter.b` | JSON embed модели | Всегда live |
| Static 40-hex key | Viewer JS на static.sketchfab.com | Каждый download + кэш `tools/wasm/static_key.txt` |
| `decrypt.wasm` | Вшит в viewer JS | В репозитории; переизвлекается если нет / при сбое decrypt |

Если что-то не работает — начните с `python main.py --check-tools` (или Docker-аналога) и раздела [Частые вопросы](#частые-вопросы-и-ошибки).
