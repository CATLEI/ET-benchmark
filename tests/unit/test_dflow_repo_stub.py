"""Tests for Bohrium artifact repo stub used by convert_to_argo."""

from copy import deepcopy

from dflow import s3_config as dflow_s3_config, set_s3_config

from et_dflow.infrastructure.workflows.dflow_repo_stub import ensure_bohr_artifact_repo_stub


def test_ensure_stub_normalizes_bare_dict_and_allows_key_assignment(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    set_s3_config(repo_key="oss-bohrium", repo={}, repo_type="s3")

    summary = ensure_bohr_artifact_repo_stub()

    assert summary["fixed"] is True
    assert dflow_s3_config["repo"] == {"oss": {}}
    assert dflow_s3_config["repo_type"] == "oss"

    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "prefix/{{workflow.name}}/{{pod.name}}"
    assert loc["oss"]["key"] == "prefix/{{workflow.name}}/{{pod.name}}"
    # ensure did not mutate the live nested dict via the smoke check
    assert "key" not in dflow_s3_config["repo"]["oss"]


def test_ensure_stub_rewrites_string_repo(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    set_s3_config(repo_key="oss-bohrium", repo="{}", repo_type="oss")

    summary = ensure_bohr_artifact_repo_stub()

    assert summary["fixed"] is True
    assert isinstance(dflow_s3_config["repo"], dict)
    assert isinstance(dflow_s3_config["repo"]["oss"], dict)

    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "x"
    assert loc["oss"]["key"] == "x"


def test_ensure_stub_skips_non_bohr(monkeypatch):
    monkeypatch.delenv("DFLOW_S3_REPO_KEY", raising=False)
    monkeypatch.delenv("BOHRIUM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("BOHRIUM_USERNAME", raising=False)
    monkeypatch.delenv("BOHRIUM_TICKET", raising=False)
    set_s3_config(repo_key=None, repo=None, repo_type="s3", storage_client=None)

    summary = ensure_bohr_artifact_repo_stub()

    assert summary.get("skipped") is True
    assert dflow_s3_config.get("repo_type") == "s3"
