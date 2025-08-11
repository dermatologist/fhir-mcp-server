# syntax=docker/dockerfile:1.7

# Use uv's Python base image (includes uv + CPython)
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim


# Copy only dependency metadata first for caching
COPY . .

# Sync (install) only runtime deps into a local .venv
# Use a build cache mount for uv to speed subsequent builds
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


# Create non-root user (UID 10001 to match prior image)
RUN useradd -m -u 10001 appuser
USER 10001

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/src \
    PATH="/.venv/bin:${PATH}"

EXPOSE 8000

# Healthcheck (adjust path/port if app offers one)
# HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
#   CMD python -c "import socket; import sys; s=socket.socket(); \
#   s.settimeout(2); \
#   s.connect(('127.0.0.1',8000)); s.close()" || exit 1

# Run installed console script from the virtual environment
CMD ["uv", "run", "fhir-mcp-server"]