# Layer ET-dflow adapter on DeepDeWedge image (keeps upstream torch stack).
#
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL``.
#
# Build from repository root:
#   docker build -f docker/algorithms/deepdewedge/Dockerfile -t et-dflow/deepdewedge:latest .
#
# Override base:
#   --build-arg BASE_IMAGE=registry.dp.tech/davinci/deepdewedge:20260113145259

ARG BASE_IMAGE=registry.dp.tech/davinci/deepdewedge:20260113145259
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/deepdewedge/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/deepdewedge/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
