"""Tests for pre-import dflow environment bootstrap."""

import os

from et_dflow.infrastructure.workflows.dflow_bootstrap import bootstrap_dflow_env


def test_bootstrap_sets_repo_json_when_bohr_without_token(monkeypatch):
    monkeypatch.setenv("BOHRIUM_ACCESS_KEY", "dummy")
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    monkeypatch.delenv("DFLOW_S3_REPO", raising=False)

    bootstrap_dflow_env({"s3_repo_key": "oss-bohrium"})

    assert os.environ["DFLOW_S3_REPO"] == "{}"


def test_bootstrap_keeps_repo_when_token_present(monkeypatch):
    monkeypatch.setenv("BOHRIUM_ACCESS_KEY", "dummy")
    monkeypatch.setenv("DFLOW_TOKEN", "tok")
    monkeypatch.delenv("DFLOW_S3_REPO", raising=False)

    bootstrap_dflow_env({"s3_repo_key": "oss-bohrium"})

    assert "DFLOW_S3_REPO" not in os.environ


def test_bootstrap_upgrades_http_host_from_yaml(monkeypatch):
    monkeypatch.delenv("DFLOW_HOST", raising=False)
    monkeypatch.delenv("DFLOW_K8S_API_SERVER", raising=False)
    monkeypatch.delenv("BOHRIUM_ACCESS_KEY", raising=False)

    bootstrap_dflow_env(
        {
            "host": "http://workflows.deepmodeling.com",
            "k8s_api_server": "http://workflows.deepmodeling.com",
            "s3_repo_key": "oss-bohrium",
        }
    )

    assert os.environ["DFLOW_HOST"] == "https://workflows.deepmodeling.com"
    assert os.environ["DFLOW_K8S_API_SERVER"] == "https://workflows.deepmodeling.com"
