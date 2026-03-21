# ET-dflow adapter on WUCon image (expects code under /opt/wucon/src).
# No local repo? Use ``Dockerfile.bohr`` + ``ET_DFLOW_REPO_URL``.
# Build from repo root:
#   docker build -f docker/algorithms/wucon/Dockerfile -t et-dflow/wucon:latest .

ARG BASE_IMAGE=registry.dp.tech/davinci/wucon:20260113160259
FROM ${BASE_IMAGE}

USER root
WORKDIR /app

COPY requirements-etdflow-algorithm.txt /tmp/requirements-etdflow-algorithm.txt
COPY et_dflow/ ./et_dflow/
COPY setup.py pyproject.toml ./

RUN pip install --no-cache-dir -r /tmp/requirements-etdflow-algorithm.txt \
    && pip install --no-cache-dir --no-deps -e .

COPY docker/algorithms/wucon/run_algorithm.py /app/run_algorithm.py
COPY docker/algorithms/wucon/docker-entrypoint.sh /app/docker-entrypoint.sh
RUN chmod +x /app/docker-entrypoint.sh

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD []
