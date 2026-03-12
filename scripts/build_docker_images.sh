#!/bin/bash
# Build script for Docker images

set -e

REGISTRY="${DOCKER_REGISTRY:-docker.io}"
IMAGE_PREFIX="${IMAGE_PREFIX:-et-dflow}"

ALGORITHMS=("wbp" "sirt" "genfire" "resire")

for alg in "${ALGORITHMS[@]}"; do
    echo "Building Docker image for $alg..."
    docker build -t "$REGISTRY/$IMAGE_PREFIX/$alg:latest" \
        -f "docker/algorithms/$alg/Dockerfile" .
done

echo "All Docker images built successfully!"

