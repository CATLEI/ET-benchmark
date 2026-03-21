# ET-dflow adapter on ASTRA Toolbox image.
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL``.
# Build from repo root:
#   docker build -f docker/algorithms/astra/Dockerfile -t et-dflow/astra:latest .

ARG BASE_IMAGE=registry.dp.tech/davinci/astra-toolbox:20260113161211
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/astra/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/astra/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
