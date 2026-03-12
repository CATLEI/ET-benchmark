# Dockerfile for RESIRE algorithm
# Build context should be the project root directory (.)
# Build command: docker build -f docker/algorithms/resire/Dockerfile -t et-dflow/resire:latest .

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

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy et_dflow package (needed for RESIRE algorithm)
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Install et_dflow package
RUN pip install --no-cache-dir -e .

FROM docker.1ms.run/python:3.10-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy et_dflow package
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Copy algorithm entry point script
COPY docker/algorithms/resire/run_algorithm.py /app/run_algorithm.py

# Copy and set entrypoint script (allows running other commands)
COPY docker/algorithms/resire/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set entrypoint (allows running python --version or other commands)
# Default: runs algorithm script
# Override: docker run et-dflow/resire:latest python --version
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []

