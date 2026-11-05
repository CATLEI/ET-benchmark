"""Tests for Bohrium artifact repo stub used by convert_to_argo."""

from copy import deepcopy

from dflow import config as dflow_config
from dflow import s3_config as dflow_s3_config, set_s3_config

from et_dflow.infrastructure.workflows.dflow_repo_stub import (
    bohr_workflow_kwargs,
    ensure_bohr_artifact_repo_stub,
)


def test_ensure_stub_normalizes_bare_dict_and_allows_key_assignment(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    set_s3_config(repo_key="oss-bohrium", repo={}, repo_type="s3")

    summary = ensure_bohr_artifact_repo_stub()

    assert summary["fixed"] is True
    assert dflow_s3_config["repo"] == {"oss": {}}
    assert dflow_s3_config["repo_type"] == "oss"
    # Empty token: clear repo_key so Workflow.__init__ → parse_repo is a no-op.
    assert dflow_s3_config["repo_key"] is None
    assert summary["cleared_repo_key"] is True

    loc = deepcopy(dflow_s3_config["repo"])
    loc[dflow_s3_config["repo_type"]]["key"] = "prefix/{{workflow.name}}/{{pod.name}}"
    assert loc["oss"]["key"] == "prefix/{{workflow.name}}/{{pod.name}}"
    # ensure did not mutate the live nested dict via the smoke check
    assert "key" not in dflow_s3_config["repo"]["oss"]


def test_ensure_stub_keeps_repo_key_when_token_present(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.setenv("DFLOW_TOKEN", "tok")
    dflow_config["token"] = "tok"
    set_s3_config(repo_key="oss-bohrium", repo={"oss": {}}, repo_type="oss")

    summary = ensure_bohr_artifact_repo_stub()

    assert dflow_s3_config["repo_key"] == "oss-bohrium"
    assert summary.get("cleared_repo_key") is False


def test_ensure_stub_rewrites_string_repo(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
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


def test_bohr_workflow_kwargs_sets_artifact_repo_key_none(monkeypatch):
    monkeypatch.setenv("DFLOW_S3_REPO_KEY", "oss-bohrium")
    monkeypatch.delenv("DFLOW_TOKEN", raising=False)
    dflow_config["token"] = ""
    set_s3_config(repo_key="oss-bohrium", repo=None, repo_type="s3")

    kwargs = bohr_workflow_kwargs(name="wf")

    assert kwargs["name"] == "wf"
    assert kwargs["artifact_repo_key"] is None
    assert dflow_s3_config["repo"] == {"oss": {}}
