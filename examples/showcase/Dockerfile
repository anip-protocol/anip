FROM python:3.12-slim

ARG SHOWCASE_APP=travel

WORKDIR /app

# The ANIP release to install. The release workflow passes the version it
# just published, so an image never carries an older runtime than its tag.
ARG ANIP_VERSION

# Install ANIP packages from PyPI + server deps
RUN test -n "$ANIP_VERSION" || { echo "ANIP_VERSION build arg is required (e.g. --build-arg ANIP_VERSION=0.24.20)"; exit 1; }
RUN pip install --no-cache-dir \
    "anip-service==${ANIP_VERSION}" \
    "anip-fastapi==${ANIP_VERSION}" \
    "anip-rest==${ANIP_VERSION}" \
    "anip-graphql==${ANIP_VERSION}" \
    "anip-mcp==${ANIP_VERSION}" \
    "anip-studio==${ANIP_VERSION}" \
    "anip-stdio==${ANIP_VERSION}" \
    uvicorn httpx

# Copy the showcase app
COPY ${SHOWCASE_APP}/ /app/

# Ephemeral demo — fresh state on every container restart
ENV ANIP_STORAGE=":memory:"
ENV ANIP_TRUST_LEVEL="signed"
ENV ANIP_KEY_PATH="/tmp/anip-keys"
ENV PORT=9100

EXPOSE 9100

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "9100"]
