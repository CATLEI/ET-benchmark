"""Bohrium artifact-repo handling for empty-token and ConfigMap fetch.

dflow ``Workflow.__init__`` calls ``parse_repo(artifact_repo_key)`` when
``repo_key`` is set and ``s3_config["repo"] is None``. That reads K8s
ConfigMap ``artifact-repositories``.

Historical workaround: nest ``{"oss": {}}`` so ``convert_to_argo`` can assign
``loc["oss"]["key"]`` without ConfigMap. That was enough to *submit*, but Argo
pods then fail with::

    failed to load artifact '...': You need to configure artifact storage

because the empty stub was paired with clearing ``artifact_repo_key``, so the
workflow had neither real OSS credentials nor ``artifactRepositoryRef:
oss-bohrium``.

Correct approach now that Bohrium ``Brm-Ticket`` can reach the gateway:

1. Keep ``repo_key=oss-bohrium`` so the workflow sets ``artifactRepositoryRef``.
2. After auth headers are attached, fetch the real ConfigMap via ``parse_repo``.
3. Only fall back to ``{"oss": {}}`` if ConfigMap fetch still fails (submit may
   work; artifact load likely will not — warn loudly).
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Optional

from dflow import config as dflow_config
from dflow import s3_config as dflow_s3_config, set_s3_config

_BOHR_ARTIFACT_REPO_STUB: Dict[str, Any] = {"oss": {}}
_BOHR_ARTIFACT_REPO_TYPE = "oss"
_BOHR_DEFAULT_REPO_KEY = "oss-bohrium"


def _is_bohr_s3_config() -> bool:
    """True when current s3/env settings indicate Bohrium/Tiefblue."""
    storage = dflow_s3_config.get("storage_client")
    storage_name = type(storage).__name__ if storage is not None else ""
    return bool(
        dflow_s3_config.get("repo_key") == _BOHR_DEFAULT_REPO_KEY
        or os.getenv("DFLOW_S3_REPO_KEY") == _BOHR_DEFAULT_REPO_KEY
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


def _desired_repo_key() -> str:
    return (
        dflow_s3_config.get("repo_key")
        or os.getenv("DFLOW_S3_REPO_KEY")
        or _BOHR_DEFAULT_REPO_KEY
    )


def _is_empty_oss_stub(repo: Any) -> bool:
    """True for missing/invalid repo or placeholder ``{"oss": {}}`` without storage fields."""
    if repo is None:
        return True
    if not isinstance(repo, dict):
        return True
    oss = repo.get("oss")
    if not isinstance(oss, dict):
        return True
    # Real ConfigMap entries typically include endpoint/bucket/keyFormat/accessKeySecret…
    meaningful = {
        k
        for k, v in oss.items()
        if k != "key" and v not in (None, "", {}, [])
    }
    return len(meaningful) == 0


def _apply_parsed_repo(repo: Dict[str, Any]) -> None:
    """Mirror dflow ``parse_repo`` side effects for repo_type / repo_prefix."""
    set_s3_config(repo=repo)
    if "s3" in repo:
        set_s3_config(repo_type="s3")
        storage = repo["s3"]
    elif "oss" in repo:
        set_s3_config(repo_type="oss")
        storage = repo["oss"]
    else:
        return
    key_format = storage.get("keyFormat") if isinstance(storage, dict) else None
    if isinstance(key_format, str):
        suffix = "{{workflow.name}}/{{pod.name}}"
        if key_format.endswith(suffix):
            set_s3_config(repo_prefix=key_format[: -len(suffix)])


def _try_parse_repo(repo_key: str) -> bool:
    """Fetch artifact-repositories ConfigMap into ``s3_config["repo"]``.

    Stock ``get_k8s_client`` only sends ``Authorization: Bearer`` when
    ``DFLOW_TOKEN`` is set — it ignores Bohrium ``Brm-Ticket`` in
    ``http_headers``. Workflow submit works with ticket because we inject
    headers into the Argo client; ConfigMap fetch must do the same, so we
    GET the ConfigMap with ``requests`` + ``dflow_config["http_headers"]``.
    """
    import yaml

    try:
        import requests
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception as exc:
        print(f"[et-dflow] ConfigMap fetch deps missing: {exc}", flush=True)
        return False

    namespace = str(dflow_config.get("namespace") or "argo")
    host = (
        str(dflow_config.get("k8s_api_server") or dflow_config.get("host") or "")
        .rstrip("/")
    )
    if not host:
        print("[et-dflow] ConfigMap fetch skipped: no k8s/host", flush=True)
        return False

    url = f"{host}/api/v1/namespaces/{namespace}/configmaps/artifact-repositories"
    headers = dict(dflow_config.get("http_headers") or {})
    token = _dflow_token()
    if token and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {token}"

    try:
        rsp = requests.get(url, headers=headers, timeout=60, verify=False)
    except Exception as exc:
        print(
            f"[et-dflow] ConfigMap GET failed ({url}): {exc}",
            flush=True,
        )
        return False

    if rsp.status_code != 200:
        body_head = (rsp.text or "")[:180].replace("\n", " ")
        print(
            "[et-dflow] ConfigMap artifact-repositories HTTP "
            f"{rsp.status_code}: {body_head}",
            flush=True,
        )
        return False

    try:
        payload = rsp.json()
        data = payload.get("data") or {}
        raw = data.get(repo_key)
        if not raw:
            print(
                f"[et-dflow] ConfigMap missing key {repo_key!r}; "
                f"have={sorted(data.keys())}",
                flush=True,
            )
            return False
        repo = yaml.safe_load(raw)
    except Exception as exc:
        print(f"[et-dflow] ConfigMap parse failed: {exc}", flush=True)
        return False

    if not isinstance(repo, dict) or _is_empty_oss_stub(repo):
        print(
            "[et-dflow] ConfigMap repo empty/invalid after parse",
            flush=True,
        )
        return False

    set_s3_config(repo_key=repo_key)
    _apply_parsed_repo(repo)
    print(
        "[et-dflow] loaded artifact repo from ConfigMap:",
        {
            "repo_key": repo_key,
            "repo_type": dflow_s3_config.get("repo_type"),
            "oss_keys": sorted((repo.get("oss") or {}).keys())
            if isinstance(repo.get("oss"), dict)
            else None,
        },
        flush=True,
    )
    return True


def ensure_bohr_artifact_repo_stub() -> Dict[str, Any]:
    """Ensure Bohrium ``s3_config`` can convert_to_argo *and* Argo can load artifacts.

    Prefer the real ``oss-bohrium`` ConfigMap (needs Brm-Ticket or DFLOW_TOKEN on
    the Argo/K8s client). Fall back to nested ``{"oss": {}}`` only if fetch fails,
    and **keep** ``repo_key`` so the workflow still gets ``artifactRepositoryRef``.
    """
    if not _is_bohr_s3_config():
        return {"skipped": True}

    repo_key = _desired_repo_key()
    set_s3_config(repo_key=repo_key)

    summary: Dict[str, Any] = {
        "repo_key": repo_key,
        "fetched_configmap": False,
        "used_stub": False,
        "fixed": False,
        "cleared_repo_key": False,
        "token_len": len(_dflow_token()),
    }

    repo = dflow_s3_config.get("repo")
    need_fetch = _is_empty_oss_stub(repo)
    if need_fetch:
        if _try_parse_repo(repo_key):
            summary["fetched_configmap"] = True
            summary["fixed"] = True
        else:
            set_s3_config(
                repo=deepcopy(_BOHR_ARTIFACT_REPO_STUB),
                repo_type=_BOHR_ARTIFACT_REPO_TYPE,
                repo_key=repo_key,
            )
            summary["used_stub"] = True
            summary["fixed"] = True
            print(
                "[et-dflow] WARNING: using empty oss stub with artifactRepositoryRef="
                f"{repo_key}. Submit may succeed, but pods can still fail with "
                "'configure artifact storage' if the cluster cannot resolve that "
                "ref. Fix: ensure Brm-Ticket/DFLOW_TOKEN can read ConfigMap "
                "artifact-repositories.",
                flush=True,
            )
    elif dflow_s3_config.get("repo_type") != _BOHR_ARTIFACT_REPO_TYPE and isinstance(
        (dflow_s3_config.get("repo") or {}).get("oss"), dict
    ):
        set_s3_config(repo_type=_BOHR_ARTIFACT_REPO_TYPE)
        summary["fixed"] = True

    # Smoke-check convert_to_argo assignment without mutating live repo.
    live = dflow_s3_config.get("repo")
    if isinstance(live, dict) and isinstance(live.get(dflow_s3_config.get("repo_type")), dict):
        loc = deepcopy(live)
        loc[dflow_s3_config["repo_type"]]["key"] = "et-dflow-stub-check"

    summary["repo"] = dflow_s3_config.get("repo")
    summary["repo_type"] = dflow_s3_config.get("repo_type")
    summary["repo_key"] = dflow_s3_config.get("repo_key")
    print("[et-dflow debug] Bohrium artifact repo stub:", summary, flush=True)
    return summary


def finalize_bohr_artifact_repo_for_submit() -> Dict[str, Any]:
    """Before ``workflow.submit()``: prefer real ConfigMap; never embed empty oss.

    Empty ``{"oss": {}}`` as ``archive_location`` makes Argo pods fail with
    "configure artifact storage". If ConfigMap is still unreachable, clear
    ``repo`` so ``convert_to_argo`` sets ``archive_location=None`` and the
    workflow ``artifactRepositoryRef: oss-bohrium`` supplies storage on cluster.
    """
    if not _is_bohr_s3_config():
        return {"skipped": True}

    summary = ensure_bohr_artifact_repo_stub()
    repo_key = dflow_s3_config.get("repo_key") or _desired_repo_key()
    set_s3_config(repo_key=repo_key)

    if _is_empty_oss_stub(dflow_s3_config.get("repo")):
        # Drop stub so ScriptOPTemplate.convert_to_argo uses loc=None.
        set_s3_config(repo=None, repo_type=_BOHR_ARTIFACT_REPO_TYPE, repo_key=repo_key)
        summary["cleared_stub_for_submit"] = True
        print(
            "[et-dflow] cleared empty oss stub before submit; "
            f"Argo will use artifactRepositoryRef={repo_key}",
            flush=True,
        )
    summary["repo"] = dflow_s3_config.get("repo")
    summary["repo_key"] = dflow_s3_config.get("repo_key")
    summary["repo_type"] = dflow_s3_config.get("repo_type")
    print("[et-dflow debug] Bohrium artifact repo for submit:", summary, flush=True)
    return summary


def bohr_workflow_kwargs(**kwargs: Any) -> Dict[str, Any]:
    """Return kwargs for ``Workflow(...)`` with Bohrium artifactRepositoryRef kept."""
    ensure_bohr_artifact_repo_stub()
    out = dict(kwargs)
    if _is_bohr_s3_config():
        # CRITICAL: do not pass None — Argo needs artifactRepositoryRef=oss-bohrium
        # when the client-side repo is only a stub or key-only OSS artifact.
        out.setdefault(
            "artifact_repo_key",
            dflow_s3_config.get("repo_key") or _BOHR_DEFAULT_REPO_KEY,
        )
        try:
            from dflow import config as _dflow_config

            if not (_dflow_config.get("token") or "").strip():
                _dflow_config["token"] = None
        except Exception:
            pass
        out.pop("token", None)
    return out
