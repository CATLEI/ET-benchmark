# Layer ET-dflow adapter on top of a GPU TIGRE image.
#
# If the build **cannot** access the full ET-dflow tree (no COPY context), use
# ``Dockerfile.bohr`` with ``--build-arg ET_DFLOW_REPO_URL=...`` to clone at build time.
#
# Build from repository root:
#   docker build -f docker/algorithms/tigre/Dockerfile -t et-dflow/tigre:latest .
#
# Override upstream base (e.g. your registry):
#   docker build -f docker/algorithms/tigre/Dockerfile \
#     --build-arg BASE_IMAGE=registry.dp.tech/davinci/tigre:20260113153441 \
#     -t your-registry/et-dflow/tigre:latest .

ARG BASE_IMAGE=registry.dp.tech/davinci/tigre:20260113153441
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/tigre/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/tigre/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
