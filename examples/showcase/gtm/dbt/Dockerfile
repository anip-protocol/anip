from python:3.12-slim

workdir /app

copy requirements.txt /tmp/requirements.txt
run pip install --no-cache-dir -r /tmp/requirements.txt

copy . /app
