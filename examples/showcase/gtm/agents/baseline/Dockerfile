from python:3.12-slim

workdir /workspace

copy packages/python /workspace/packages/python
copy examples/showcase/gtm/agents/baseline /workspace/examples/showcase/gtm/agents/baseline
copy examples/showcase/gtm/ui/app /workspace/examples/showcase/gtm/ui/app

run pip install --no-cache-dir \
    fastapi \
    uvicorn \
    httpx

workdir /workspace/examples/showcase/gtm/agents/baseline

cmd ["python", "app.py"]
