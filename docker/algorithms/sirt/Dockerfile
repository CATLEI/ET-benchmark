# Dockerfile for SIRT (Simultaneous Iterative Reconstruction Technique) algorithm

FROM python:3.11-slim as builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy et_dflow package (needed for SIRT algorithm)
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

# Install et_dflow package
RUN pip install --no-cache-dir -e .

# Copy algorithm entry point script
COPY docker/algorithms/sirt/run_algorithm.py /app/run_algorithm.py

# Copy and set entrypoint script (allows running other commands)
COPY docker/algorithms/sirt/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

# Set entrypoint (allows running python --version or other commands)
# Default: runs algorithm script
# Override: docker run et-dflow/sirt:latest python --version
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []

