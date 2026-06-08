from python:3.12-slim

workdir /workspace

copy examples/showcase/gtm/agents/manifest_aware /workspace/examples/showcase/gtm/agents/manifest_aware
copy examples/showcase/gtm/ui/app /workspace/examples/showcase/gtm/ui/app

run pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx

workdir /workspace/examples/showcase/gtm/agents/manifest_aware

cmd ["python", "app.py"]
