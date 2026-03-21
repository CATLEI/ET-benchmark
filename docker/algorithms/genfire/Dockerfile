# Layer ET-dflow adapter on GENFIRE-Python image.
#
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL`` (see tigre/Dockerfile.bohr).
#
# Build from repository root:
#   docker build -f docker/algorithms/genfire/Dockerfile -t et-dflow/genfire:latest .
#
# Override base:
#   --build-arg BASE_IMAGE=registry.dp.tech/davinci/genfire-python:20260110195114

ARG BASE_IMAGE=registry.dp.tech/davinci/genfire-python:20260110195114
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/genfire/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/genfire/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
