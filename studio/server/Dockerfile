FROM python:3.12-slim
WORKDIR /app
COPY studio/server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY studio/ /app/studio/
COPY tooling/ /app/tooling/
COPY packages/python/ /app/packages/python/
RUN pip install --no-cache-dir \
    /app/packages/python/anip-core \
    /app/packages/python/anip-crypto \
    /app/packages/python/anip-server \
    /app/packages/python/anip-service \
    /app/packages/python/anip-fastapi
ENV PYTHONPATH=/app
EXPOSE 8100
CMD ["uvicorn", "studio.server.app:app", "--host", "0.0.0.0", "--port", "8100"]
