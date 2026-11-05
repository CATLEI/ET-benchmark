"""Tests for Bohrium artifact repo stub / ConfigMap fetch helpers."""

from copy import deepcopy

from dflow import config as dflow_config
from dflow import s3_config as dflow_s3_config, set_s3_config

from et_dflow.infrastructure.workflows.dflow_repo_stub import (
    _is_empty_oss_stub,
    bohr_workflow_kwargs,
    ensure_bohr_artifact_repo_stub,
    finalize_bohr_artifact_repo_for_submit,
)


def test_is_empty_oss_stub():
    assert _is_empty_oss_stub(None) is True
    assert _is_empty_oss_stub({}) is True
    assert _is_empty_oss_stub({"oss": {}}) is True
    assert _is_empty_oss_stub({"oss": {"key": "only"}}) is True
    assert _is_empty_oss_stub({"oss": {"endpoint": "https://x", "bucket": "b"}}) is False


def _forbid_configmap(monkeypatch):
    class _Rsp:
        status_code = 403
        text = "<html>403</html>"

        def json(self):
            return {}

    monkeypatch.setattr("requests.get", lambda *a, **k: _Rsp())


def test_ensure_stub_keeps_repo_key_and_falls_back(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    dflow_config["host"] = "https://workflows.deepmodeling.com"
    dflow_config["k8s_api_server"] = "https://workflows.deepmodeling.com"
    dflow_config["http_headers"] = {"Brm-Ticket": "t"}
    set_s3_config(repo_key="oss-bohrium", repo={}, repo_type="s3")
    _forbid_configmap(monkeypatch)

    summary = ensure_bohr_artifact_repo_stub()

    assert summary["used_stub"] is True
    assert summary["cleared_repo_key"] is False
    assert dflow_s3_config["repo"] == {"oss": {}}
    assert dflow_s3_config["repo_type"] == "oss"
    assert dflow_s3_config["repo_key"] == "oss-bohrium"

    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "prefix/{{workflow.name}}/{{pod.name}}"
    assert loc["oss"]["key"] == "prefix/{{workflow.name}}/{{pod.name}}"
    assert "key" not in dflow_s3_config["repo"]["oss"]


def test_ensure_uses_configmap_when_fetch_succeeds(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    dflow_config["host"] = "https://workflows.deepmodeling.com"
    dflow_config["k8s_api_server"] = "https://workflows.deepmodeling.com"
    dflow_config["namespace"] = "argo"
    dflow_config["http_headers"] = {"Brm-Ticket": "t"}
    set_s3_config(repo_key="oss-bohrium", repo={"oss": {}}, repo_type="oss")

    raw = (
        "oss:\n"
        "  endpoint: https://example.aliyuncs.com\n"
        "  bucket: bohrium\n"
        "  keyFormat: foo/{{workflow.name}}/{{pod.name}}\n"
    )

    class _Rsp:
        status_code = 200
        text = "ok"

        def json(self):
            return {"data": {"oss-bohrium": raw}}

    monkeypatch.setattr("requests.get", lambda *a, **k: _Rsp())

    summary = ensure_bohr_artifact_repo_stub()

    assert summary["fetched_configmap"] is True
    assert summary["used_stub"] is False
    assert dflow_s3_config["repo"]["oss"]["bucket"] == "bohrium"
    assert dflow_s3_config["repo_key"] == "oss-bohrium"
    assert dflow_s3_config["repo_type"] == "oss"


def test_ensure_stub_skips_non_bohr(monkeypatch):
    monkeypatch.delenv("DFLOW_S3_REPO_KEY", raising=False)
    monkeypatch.delenv("BOHRIUM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("BOHRIUM_USERNAME", raising=False)
    monkeypatch.delenv("BOHRIUM_TICKET", raising=False)
    set_s3_config(repo_key=None, repo=None, repo_type="s3", storage_client=None)

    summary = ensure_bohr_artifact_repo_stub()

    assert summary.get("skipped") is True
    assert dflow_s3_config.get("repo_type") == "s3"


def test_bohr_workflow_kwargs_keeps_artifact_repo_key(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    dflow_config["host"] = "https://workflows.deepmodeling.com"
    dflow_config["k8s_api_server"] = "https://workflows.deepmodeling.com"
    dflow_config["http_headers"] = {"Brm-Ticket": "t"}
    set_s3_config(repo_key="oss-bohrium", repo=None, repo_type="s3")
    _forbid_configmap(monkeypatch)

    kwargs = bohr_workflow_kwargs(name="wf")

    assert kwargs["name"] == "wf"
    assert kwargs["artifact_repo_key"] == "oss-bohrium"
    assert dflow_s3_config["repo_key"] == "oss-bohrium"


def test_finalize_clears_stub_when_configmap_unreachable(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    dflow_config["host"] = "https://workflows.deepmodeling.com"
    dflow_config["k8s_api_server"] = "https://workflows.deepmodeling.com"
    dflow_config["namespace"] = "argo"
    dflow_config["http_headers"] = {"Brm-Ticket": "t"}
    set_s3_config(repo_key="oss-bohrium", repo={"oss": {}}, repo_type="oss")
    _forbid_configmap(monkeypatch)

    summary = finalize_bohr_artifact_repo_for_submit()

    assert summary.get("cleared_stub_for_submit") is True
    assert dflow_s3_config["repo"] is None
    assert dflow_s3_config["repo_key"] == "oss-bohrium"
    assert dflow_s3_config["repo_type"] == "oss"
