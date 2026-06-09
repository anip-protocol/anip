from python:3.12-slim

workdir /workspace

copy packages/python /workspace/packages/python
copy examples/showcase/gtm/services/gtm_pipeline /workspace/examples/showcase/gtm/services/gtm_pipeline

run pip install --no-cache-dir \
    -e /workspace/packages/python/anip-core \
    -e /workspace/packages/python/anip-crypto \
    -e /workspace/packages/python/anip-server \
    -e /workspace/packages/python/anip-service \
    -e /workspace/packages/python/anip-fastapi \
    -e /workspace/packages/python/anip-rest \
    -e /workspace/packages/python/anip-graphql \
    -e /workspace/packages/python/anip-mcp \
    -e /workspace/packages/python/anip-studio \
    uvicorn \
    psycopg[binary]

workdir /workspace/examples/showcase/gtm/services/gtm_pipeline

cmd ["python", "app.py"]
