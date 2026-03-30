FROM python:3.12-slim

ARG SHOWCASE_APP=travel

WORKDIR /app

# Install ANIP packages from PyPI + server deps
RUN pip install --no-cache-dir \
    anip-service \
    anip-fastapi \
    anip-rest \
    anip-graphql \
    anip-mcp \
    anip-studio \
    anip-stdio \
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
