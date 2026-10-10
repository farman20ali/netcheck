# netcheck — Production Dockerfile
# ============================================================
# Multi-stage build for a minimal, hardened container image.
#
# Usage:
#   docker build -t netcheck:latest .
#   docker run --rm netcheck:latest ping google.com
#   docker run --rm netcheck:latest http https://example.com
#   docker run --rm netcheck:latest --help
#
# Run as non-root (uid 1000 / gid 1000) with no shell by default.
# Raw sockets (for ping / MTR) require --cap-add=NET_RAW.
# ============================================================

# ---- Stage 1: builder -------------------------------------------
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml README.md ./
COPY netcheck/ netcheck/

# Build wheel (no runtime dependencies → pure-stdlib wheel)
RUN pip install --upgrade pip build \
    && python -m build --wheel --outdir /dist .

# ---- Stage 2: runtime -------------------------------------------
FROM python:3.12-slim AS runtime

# Security: run as a non-root user
RUN groupadd -r netcheck --gid=1000 \
    && useradd -r -g netcheck --uid=1000 --no-create-home --shell=/bin/false netcheck

# Install the built wheel
COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

# Metadata
LABEL org.opencontainers.image.title="netcheck" \
      org.opencontainers.image.description="Comprehensive network connectivity checker" \
      org.opencontainers.image.source="https://github.com/farman20ali/netcheck" \
      org.opencontainers.image.licenses="MIT"

USER netcheck

# Default command shows help
ENTRYPOINT ["netcheck"]
CMD ["--help"]
