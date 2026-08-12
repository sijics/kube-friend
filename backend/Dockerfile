# ── Stage 1: builder ──────────────────────────────────────────────────────────
# We use a builder stage to install dependencies with uv.
# This keeps the final image lean — only the installed packages are copied over.
FROM python:3.12-slim AS builder

# Install uv — the fast Python package manager we chose over pip
# uv is ~10-100x faster than pip and produces a reproducible lock file
RUN pip install uv

WORKDIR /app

# Copy dependency files first (before source code).
# Docker caches each layer. If neither file has changed, this layer
# is reused on the next build — so `uv sync` only re-runs when deps change.
# uv.lock pins exact versions; pyproject.toml declares the constraints.
# Both are needed: pyproject.toml for the project metadata, uv.lock for frozen installs.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Copy the installed virtual environment from the builder stage
COPY --from=builder /app/.venv /app/.venv

# Copy the application source code
COPY app/ ./app/

# Make the venv's binaries available on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Expose the port FastAPI will listen on
EXPOSE 8000

# Start uvicorn — the ASGI server that runs FastAPI
# --host 0.0.0.0 makes it reachable from outside the container
# --reload is off in production; we'll add it via compose override for dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
