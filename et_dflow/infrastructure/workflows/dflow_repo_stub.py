"""Bohrium artifact-repo stub for empty-token convert_to_argo.

dflow does ``loc = deepcopy(repo); loc[repo_type]["key"] = ...``.
A bare ``{}`` or string stub raises; nested ``{"oss": {}}`` with
``repo_type="oss"`` is enough when Tiefblue handles real I/O.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict

from dflow import s3_config as dflow_s3_config, set_s3_config

_BOHR_ARTIFACT_REPO_STUB: Dict[str, Any] = {"oss": {}}
_BOHR_ARTIFACT_REPO_TYPE = "oss"


def _is_bohr_s3_config() -> bool:
    """True when current s3/env settings indicate Bohrium/Tiefblue."""
    storage = dflow_s3_config.get("storage_client")
    storage_name = type(storage).__name__ if storage is not None else ""
    return bool(
        dflow_s3_config.get("repo_key") == "oss-bohrium"
        or os.getenv("DFLOW_S3_REPO_KEY") == "oss-bohrium"
        or os.getenv("BOHRIUM_ACCESS_KEY")
        or os.getenv("BOHRIUM_USERNAME")
        or os.getenv("BOHRIUM_TICKET")
        or "Tiefblue" in storage_name
        or "bohrium" in storage_name.lower()
    )


def ensure_bohr_artifact_repo_stub() -> Dict[str, Any]:
    """Normalize ``s3_config`` so ``convert_to_argo`` can set ``loc["oss"]["key"]``.

    No-op for MinIO / non-Bohrium. Call after Bohrium/Tiefblue setup and again
    immediately before ``Workflow()``.
    """
    if not _is_bohr_s3_config():
        return {"skipped": True}
    repo = dflow_s3_config.get("repo")
    fixed = False
    if not isinstance(repo, dict) or not isinstance(repo.get("oss"), dict):
        set_s3_config(repo=deepcopy(_BOHR_ARTIFACT_REPO_STUB))
        fixed = True
    if dflow_s3_config.get("repo_type") != _BOHR_ARTIFACT_REPO_TYPE:
        set_s3_config(repo_type=_BOHR_ARTIFACT_REPO_TYPE)
        fixed = True
    # Smoke-check the assignment convert_to_argo performs (deepcopy: do not mutate).
    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "et-dflow-stub-check"
    summary = {
        "repo": dflow_s3_config.get("repo"),
        "repo_type": dflow_s3_config.get("repo_type"),
        "fixed": fixed,
    }
    if fixed:
        print("[et-dflow debug] Bohrium artifact repo stub normalized:", summary, flush=True)
    return summary
