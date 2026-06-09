FROM python:3.12-slim
WORKDIR /app
COPY studio/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY studio/ /app/studio/
COPY docs/examples/ /app/docs/examples/
COPY tooling/ /app/tooling/
COPY packages/python/ /app/packages/python/
RUN pip install --no-cache-dir \
    /app/packages/python/anip-core \
    /app/packages/python/anip-crypto \
    /app/packages/python/anip-server \
    /app/packages/python/anip-service \
    /app/packages/python/anip-fastapi
COPY studio/server/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh
ENV PYTHONPATH=/app
EXPOSE 8100
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8100/api/readyz', timeout=3).read()" || exit 1
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "studio.server.app:app", "--host", "0.0.0.0", "--port", "8100"]
