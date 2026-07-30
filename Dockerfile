# Sketchfab CLI Downloader — Python + Wine for Windows tools (binzDecrypt / osgconv)
FROM python:3.12-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WINEDEBUG=-all \
    WINEPREFIX=/root/.wine \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    NODE_SKIP_PLATFORM_CHECK=1 \
    DEBIAN_FRONTEND=noninteractive

# Debian places the loader at /usr/lib/wine/wine64 (not always on PATH).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wine64 \
        nodejs \
        ca-certificates \
        curl \
        cabextract \
        fonts-dejavu-core \
    && ln -sf /usr/lib/wine/wine64 /usr/bin/wine64 \
    && ln -sf /usr/lib/wine/wine64 /usr/bin/wine \
    && ln -sf /usr/lib/wine/wineserver /usr/bin/wineserver \
    && rm -rf /var/lib/apt/lists/* \
    && wine64 wineboot --init \
    && wine64 reg add "HKCU\\Software\\Wine" /v Version /t REG_SZ /d win10 /f \
    && wineserver -w || true

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py osgjs_convert.py textures.py setup_tools.py ./
COPY tools/ ./tools/

RUN mkdir -p /app/downloads

# Default: show help. Pass a URL when running the container.
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
