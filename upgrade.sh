#!/bin/bash

# Set the image name
IMAGE_NAME="cyberflix"

# Stop Docker Compose containers, prune dangling images, build image, and start stack
docker compose down && docker image prune -f && docker build -t "$IMAGE_NAME" . && docker compose up -d || { echo "Error: Failed to execute Docker commands."; exit 1; }

echo "Docker Compose stack started successfully with image $IMAGE_NAME."
