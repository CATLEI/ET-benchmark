"""Unit tests for Aliyun openresty acw_tc absorb / detect helpers."""

from types import SimpleNamespace

from dflow import config as dflow_config

from et_dflow.infrastructure.workflows.dflow_config import (
    _is_openresty_html_403,
    _merge_cookie,
    absorb_waf_cookies_from_exception,
)


def test_merge_cookie_replaces_same_key():
    assert _merge_cookie("brmToken=old; acw_tc=a", "acw_tc=b") == "brmToken=old; acw_tc=b"


def test_is_openresty_html_403_detects_edge():
    exc = SimpleNamespace(
        status=403,
        headers={
            "Server": "openresty",
            "Content-Type": "text/html",
            "Set-Cookie": "acw_tc=abc;path=/;HttpOnly;Max-Age=1800",
        },
        body="<html><head><title>403 Forbidden</title></head></html>",
    )
    assert _is_openresty_html_403(exc) is True


def test_absorb_waf_cookies_from_exception(monkeypatch):
    dflow_config["http_headers"] = {"Brm-Ticket": "t", "Cookie": "brmToken=tok"}
    exc = SimpleNamespace(
        status=403,
        headers={
            "Server": "openresty",
            "Set-Cookie": "acw_tc=2762447a17938622169034120e4217c0;path=/;HttpOnly",
        },
        body="<html>",
    )
    assert absorb_waf_cookies_from_exception(exc) is True
    cookie = dflow_config["http_headers"]["Cookie"]
    assert "brmToken=tok" in cookie
    assert "acw_tc=2762447a17938622169034120e4217c0" in cookie
    assert dflow_config["http_headers"]["Brm-Ticket"] == "t"
