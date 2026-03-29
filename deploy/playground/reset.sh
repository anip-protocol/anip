#!/bin/bash
# Reset all playground showcase containers — fresh databases, clean state
set -e
cd /opt/anip-playground
docker compose down
docker compose up -d --force-recreate
echo "$(date): Playground reset complete" >> /var/log/anip-playground-reset.log
