# Dockerfile for WBP (Weighted Back Projection) algorithm
# IMPORTANT:
# - Build context must be the project root directory (.)
# - Dockerfile path should be docker/algorithms/wbp/Dockerfile
# - This file is intended for standard Docker builds with access to the full repository context
# - For Bohr Station builds that cannot COPY local files, use docker/algorithms/wbp/Dockerfile.bohr
# - If a remote builder (for example, Bohr Station) uploads only docker/algorithms/wbp/
#   as the context, the COPY instructions for requirements.txt, setup.py,
#   pyproject.toml, and et_dflow/ will fail.
# Build command: docker build -f docker/algorithms/wbp/Dockerfile -t et-dflow/wbp:latest .

FROM docker.1ms.run/python:3.10-slim AS builder

WORKDIR /app

# Configure apt to use Chinese mirror for faster downloads
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources || \
    sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list || \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main" > /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main" >> /etc/apt/sources.list && \
    echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main" >> /etc/apt/sources.list

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies from the repository root context
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# Copy package sources from the repository root context
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Install et_dflow package
RUN pip install --no-cache-dir --timeout 300 \
    -i https://pypi.tuna.tsinghua.edu.cn/simple -e .

FROM docker.1ms.run/python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy et_dflow package
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Copy algorithm entry point script
COPY docker/algorithms/wbp/run_algorithm.py /app/run_algorithm.py

# Copy and set entrypoint script (allows running other commands)
COPY docker/algorithms/wbp/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set entrypoint (allows running python --version or other commands)
# Default: runs algorithm script
# Override: docker run et-dflow/wbp:latest python --version
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []

