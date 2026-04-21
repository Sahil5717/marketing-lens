FROM python:3.12-slim

WORKDIR /app

# System dependencies for scientific Python stack AND Node.js for the
# frontend build.
#   build-essential + gfortran: required by PyTensor (PyMC), Prophet (CmdStan)
#   libopenblas-dev:             BLAS backend for NumPy/SciPy
#   pkg-config:                  required by several pip builds
#   curl:                        healthcheck convenience + node installer
#   nodejs + npm:                builds the MarketLens client and editor
#                                React bundles via Vite
# Cleaning apt lists after install trims ~30MB from the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        gfortran \
        libopenblas-dev \
        pkg-config \
        curl \
        ca-certificates \
        gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python requirements FIRST so pip layer caches across
# code changes.
COPY backend/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Verify the critical imports actually work AFTER install.
RUN python -c "import numpy, pandas, scipy, sklearn, statsmodels, fastapi; print('[OK] core stack')"
RUN python -c "import pymc, arviz; print(f'[OK] pymc {pymc.__version__}, arviz {arviz.__version__}')"
RUN python -c "import prophet; print(f'[OK] prophet {prophet.__version__}')"

# Copy frontend package manifests FIRST so npm install layer caches across
# React code changes (same pattern as pip above).
COPY frontend/package.json frontend/package-lock.json /app/frontend/
WORKDIR /app/frontend
RUN npm ci --no-audit --no-fund

# Copy remaining application code
WORKDIR /app
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY templates/ ./templates/
COPY docs/ ./docs/
COPY LICENSE ./

# Build the three frontend entries (analyst, MarketLens client, MarketLens
# editor). Output goes to /app/frontend-dist/. The Python server picks
# this up at runtime and serves the built HTML + JS bundles as static
# files.
WORKDIR /app/frontend
RUN npm run build

# Verify the build produced what we expect. Fail fast at build time if
# any of the four entry points are missing.
RUN test -f /app/frontend-dist/index-client.html || (echo "Missing client HTML" && exit 1)
RUN test -f /app/frontend-dist/index-editor.html || (echo "Missing editor HTML" && exit 1)
RUN test -f /app/frontend-dist/index-login.html || (echo "Missing login HTML" && exit 1)
RUN test -d /app/frontend-dist/assets || (echo "Missing assets dir" && exit 1)
RUN echo "[OK] Frontend built successfully:" && ls -la /app/frontend-dist/

WORKDIR /app/backend
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/health || exit 1

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
