from python:3.12-slim

workdir /workspace

env PYTHONPATH=/workspace/examples/showcase/gtm

copy packages/python /workspace/packages/python
copy examples/showcase/gtm/shared /workspace/examples/showcase/gtm/shared
copy examples/showcase/gtm/agents/llm_runtime /workspace/examples/showcase/gtm/agents/llm_runtime
copy examples/showcase/gtm/generated/language-parity/python/agent-consumption /workspace/examples/showcase/gtm/generated/language-parity/python/agent-consumption

run pip install --no-cache-dir \
    -e /workspace/packages/python/anip-runtime-utils \
    fastapi \
    uvicorn \
    httpx

workdir /workspace/examples/showcase/gtm/agents/llm_runtime

cmd ["python", "app.py"]
