# Skylar IQ QA Tool — container image
#
# Base: Microsoft's official Playwright Python image. Chromium + all OS
# dependencies (fonts, libxkbcommon, etc.) are baked in. Keep this version
# in lock-step with the playwright pin in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.59.0-noble

WORKDIR /app

# Install Python deps first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the app + the sample questions sheet.
COPY app/ ./app/
COPY data/ ./data/

# Per-job artefacts land here. Mount a host volume to persist them.
RUN mkdir -p /app/runs

EXPOSE 5050

# Container-level health probe — useful on Render/Fly/DO/k8s.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; \
  urllib.request.urlopen('http://127.0.0.1:5050/api/runs', timeout=3); sys.exit(0)" \
  || exit 1

# Bind to 0.0.0.0 so Docker's port forwarding can reach Flask.
# --no-browser stops it trying to open a browser inside the container.
CMD ["python", "-m", "app.server", "--host", "0.0.0.0", "--port", "5050", "--no-browser"]
