# polished: a nail polish inventory fed by the Holo Taco catalog. Serves the web app on 8080.

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.12.23 /uv /usr/local/bin/uv

# The image's own Python, never a downloaded one: the venv is copied into an
# identical base below and its interpreter symlink has to resolve there.
ENV UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_PYTHON_DOWNLOADS=never \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /build
# Installed from the lock, so the image runs the versions the tests ran.
# Dependencies are their own layer so a source change does not download them again.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-editable
COPY src ./src
RUN uv sync --locked --no-editable

FROM python:3.12-slim

RUN useradd --uid 1000 --create-home --shell /usr/sbin/nologin polished \
 && mkdir -p /data \
 && chown polished:polished /data

COPY --from=builder /opt/venv /opt/venv

ARG POLISHED_VERSION=dev

# The root filesystem is read-only in the pod; /data is the writable volume.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    POLISHED_VERSION=${POLISHED_VERSION} \
    POLISHED_DB_PATH=/data/polished.db

# Fail at build time, not in the pod: the package imports from the venv copy (not a source
# tree), its bundled migrations apply to a throwaway database, and the static files (icons,
# the zxing wasm) are in the package.
RUN python -c "import polished.server; from polished.migrate import migrate; print('migrations', migrate('/tmp/selfcheck.db'))" \
 && test -s /opt/venv/lib/python3.12/site-packages/polished/static/vendor/zxing-wasm/zxing_reader.wasm \
 && test -s /opt/venv/lib/python3.12/site-packages/polished/static/icons/ui.svg \
 && rm -f /tmp/selfcheck.db*

WORKDIR /app
USER polished
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz')"

CMD ["python", "-m", "polished", "serve"]
