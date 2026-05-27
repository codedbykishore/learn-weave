#!/bin/bash
while true; do
  npx localtunnel --port 3000 2>&1
  sleep 2
done