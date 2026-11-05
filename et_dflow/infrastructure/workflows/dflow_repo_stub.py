"""Bohrium artifact-repo stub for empty-token convert_to_argo.

dflow ``Workflow.__init__`` always calls ``parse_repo(artifact_repo_key)``.
That hits K8s ConfigMap ``artifact-repositories`` when::

    repo_key is not None and s3_config["repo"] is None

With empty ``DFLOW_TOKEN`` the gateway returns openresty HTML 403.

Fix: keep nested ``{"oss": {}}`` + ``repo_type=oss`` for convert_to_argo, and
when there is no K8s token also clear ``repo_key`` / pass
``artifact_repo_key=None`` so ``parse_repo`` is a no-op. Real I/O uses
TiefblueClient.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Optional

from dflow import config as dflow_config
from dflow import s3_config as dflow_s3_config, set_s3_config

_BOHR_ARTIFACT_REPO_STUB: Dict[str, Any] = {"oss": {}}
_BOHR_ARTIFACT_REPO_TYPE = "oss"
_PARSE_REPO_PATCHED = False


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


def _dflow_token() -> str:
    return (
        (os.environ.get("DFLOW_TOKEN") or "").strip()
        or str(dflow_config.get("token") or "").strip()
    )


def _patch_parse_repo_skip_when_repo_set() -> None:
    """Belt-and-suspenders for older pydflow that still may hit ConfigMap."""
    global _PARSE_REPO_PATCHED
    if _PARSE_REPO_PATCHED:
        return
    try:
        import dflow.workflow as workflow_mod
    except Exception:
        return

    original = workflow_mod.parse_repo

    def _safe_parse_repo(repo_key=None, namespace=None, **kwargs):
        # Already have a stub/full repo → never touch ConfigMap.
        if dflow_s3_config.get("repo") is not None:
            return None
        # No K8s token → ConfigMap will 403; keep going with whatever stub we have.
        if not _dflow_token():
            if dflow_s3_config.get("repo") is None:
                set_s3_config(
                    repo=deepcopy(_BOHR_ARTIFACT_REPO_STUB),
                    repo_type=_BOHR_ARTIFACT_REPO_TYPE,
                )
            print(
                "[et-dflow] skip parse_repo ConfigMap (empty DFLOW_TOKEN; "
                "using nested oss stub)",
                flush=True,
            )
            return None
        return original(repo_key, namespace, **kwargs)

    workflow_mod.parse_repo = _safe_parse_repo
    _PARSE_REPO_PATCHED = True


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

    token = _dflow_token()
    cleared_repo_key = False
    # Empty token: Workflow.__init__ → parse_repo(repo_key) must not hit ConfigMap.
    # Clearing repo_key makes parse_repo a no-op even if repo were somehow None.
    if not token and dflow_s3_config.get("repo_key") is not None:
        set_s3_config(repo_key=None)
        cleared_repo_key = True
        fixed = True

    _patch_parse_repo_skip_when_repo_set()

    # Smoke-check the assignment convert_to_argo performs (deepcopy: do not mutate).
    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "et-dflow-stub-check"
    summary = {
        "repo": dflow_s3_config.get("repo"),
        "repo_type": dflow_s3_config.get("repo_type"),
        "repo_key": dflow_s3_config.get("repo_key"),
        "token_len": len(token),
        "cleared_repo_key": cleared_repo_key,
        "fixed": fixed,
    }
    print("[et-dflow debug] Bohrium artifact repo stub:", summary, flush=True)
    return summary


def bohr_workflow_kwargs(**kwargs: Any) -> Dict[str, Any]:
    """Return kwargs for ``Workflow(...)`` that avoid ConfigMap under empty token."""
    ensure_bohr_artifact_repo_stub()
    out = dict(kwargs)
    if _is_bohr_s3_config() and not _dflow_token():
        # Explicit None beats s3_config["repo_key"] fallback inside Workflow.__init__.
        out.setdefault("artifact_repo_key", None)
        # Empty string must not become Authorization: Bearer  (openresty 403).
        out.setdefault("token", None)
        try:
            from dflow import config as _dflow_config

            if not (_dflow_config.get("token") or "").strip():
                _dflow_config["token"] = None
        except Exception:
            pass
    return out
