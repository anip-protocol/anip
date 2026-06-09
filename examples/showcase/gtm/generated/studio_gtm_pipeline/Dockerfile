from python:3.12-slim

workdir /workspace

env PYTHONPATH=/workspace/examples/showcase/gtm

copy packages/python /workspace/packages/python
copy examples/showcase/gtm/shared /workspace/examples/showcase/gtm/shared
copy examples/showcase/gtm/generated/studio_gtm_pipeline /workspace/examples/showcase/gtm/generated/studio_gtm_pipeline

run pip install --no-cache-dir \
    -e /workspace/packages/python/anip-core \
    -e /workspace/packages/python/anip-crypto \
    -e /workspace/packages/python/anip-server \
    -e /workspace/packages/python/anip-service \
    -e /workspace/packages/python/anip-fastapi \
    uvicorn \
    psycopg[binary]

workdir /workspace/examples/showcase/gtm/generated/studio_gtm_pipeline

cmd ["python", "data_access_service.py"]
