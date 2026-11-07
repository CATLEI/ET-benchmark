# Layer the ASD-POCS adapter on a GPU TIGRE image.
#
# Build from repository root:
#   docker build -f docker/algorithms/tvm/Dockerfile -t et-dflow/tvm:latest .

ARG BASE_IMAGE=registry.dp.tech/davinci/tigre:20260113153441
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/tvm/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/tvm/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
