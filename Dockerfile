FROM python:3.11-slim

# Pinned uv so dependency resolution/installation is reproducible
COPY --from=ghcr.io/astral-sh/uv:0.10.12 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PYTHON=/usr/local/bin/python3.11 \
    PATH="/app/.venv/bin:$PATH"

# Install locked runtime dependencies first (cached unless the lock changes).
# All locked runtime deps ship manylinux x86_64 wheels for cp311, so no compiler is needed.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

# Copy project files
COPY src/ src/
COPY templates/ templates/
COPY static/ static/

# Install the project itself (non-editable) against the same locked deps
RUN uv sync --frozen --no-dev --no-editable

# Create data directory
RUN mkdir -p /app/data

EXPOSE 8000

CMD ["uvicorn", "arxivbot.main:app", "--host", "0.0.0.0", "--port", "8000"]
