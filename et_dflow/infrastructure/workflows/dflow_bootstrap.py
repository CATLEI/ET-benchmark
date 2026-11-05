"""
Environment bootstrap that must run BEFORE any ``import dflow``.

``dflow`` calls ``parse_repo()`` at import time. If ``DFLOW_S3_REPO_KEY`` is set
(e.g. ``oss-bohrium``) and ``DFLOW_TOKEN`` is missing, that hits the K8s API and
often returns an openresty HTML 403. Bohrium artifact storage uses Tiefblue and
does not need that ConfigMap read when ``DFLOW_S3_REPO`` is already non-null.
"""

from __future__ import annotations

import os
from typing import Any, Dict, Optional

_WF_HOSTS = (
    "http://workflows.deepmodeling.com",
    "https://workflows.deepmodeling.com",
)


def _is_bohr(dflow_section: Optional[Dict[str, Any]]) -> bool:
    section = dflow_section or {}
    return bool(
        os.getenv("BOHRIUM_ACCESS_KEY")
        or os.getenv("BOHRIUM_USERNAME")
        or os.getenv("BOHRIUM_TICKET")
        or os.getenv("BOHRIUM_AUTHORIZATION")
        or section.get("bohrium_access_key")
        or section.get("bohrium_username")
        or section.get("s3_repo_key") == "oss-bohrium"
        or os.getenv("DFLOW_S3_REPO_KEY") == "oss-bohrium"
        or (
            section.get("s3_storage_client")
            and "bohrium" in str(section.get("s3_storage_client")).lower()
        )
    )


def _force_https_workflow_host(var_name: str) -> None:
    value = (os.environ.get(var_name) or "").strip()
    if value == "http://workflows.deepmodeling.com":
        os.environ[var_name] = "https://workflows.deepmodeling.com"


def bootstrap_dflow_env(dflow_section: Optional[Dict[str, Any]] = None) -> None:
    """Mutate ``os.environ`` so a subsequent ``import dflow`` does not 403."""
    section = dflow_section or {}

    # Prefer https for the Bohrium/dflow gateway (http often gets WAF 403 HTML).
    for key in ("DFLOW_HOST", "DFLOW_K8S_API_SERVER", "K8S_API_SERVER"):
        _force_https_workflow_host(key)

    host = str(section.get("host") or "").strip()
    k8s = str(section.get("k8s_api_server") or "").strip()
    if host == "http://workflows.deepmodeling.com" and not os.getenv("DFLOW_HOST"):
        os.environ["DFLOW_HOST"] = "https://workflows.deepmodeling.com"
    if k8s == "http://workflows.deepmodeling.com" and not (
        os.getenv("DFLOW_K8S_API_SERVER") or os.getenv("K8S_API_SERVER")
    ):
        os.environ["DFLOW_K8S_API_SERVER"] = "https://workflows.deepmodeling.com"

    if not _is_bohr(section):
        return

    # Ensure Bohrium storage key is visible to later configure_dflow.
    if not os.getenv("DFLOW_S3_REPO_KEY") and section.get("s3_repo_key"):
        os.environ["DFLOW_S3_REPO_KEY"] = str(section["s3_repo_key"])

    # Skip import-time ConfigMap fetch when no Argo/K8s token is available.
    # TiefblueClient (configured after import) replaces artifact-repositories.
    token = (os.environ.get("DFLOW_TOKEN") or "").strip()
    if token:
        return

    # Non-null JSON makes dflow.s3_config["repo"] truthy → parse_repo no-ops.
    if not (os.environ.get("DFLOW_S3_REPO") or "").strip():
        os.environ["DFLOW_S3_REPO"] = "{}"
        print(
            "[et-dflow] DFLOW_TOKEN unset: skip dflow import-time ConfigMap "
            "parse (Bohrium/Tiefblue). Set DFLOW_TOKEN if Argo submit still 403s.",
            flush=True,
        )
