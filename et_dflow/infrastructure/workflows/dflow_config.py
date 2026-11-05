"""
dflow configuration.

Configures dflow connection and S3/storage for remote cluster mode.
Supports MinIO (self-hosted) and Bohr/Tiefblue (玻尔空间站) backends.
"""

import importlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dflow import config as dflow_config, s3_config as dflow_s3_config, set_s3_config
from et_dflow.core.config import get_config_manager
from et_dflow.infrastructure.workflows.dflow_repo_stub import ensure_bohr_artifact_repo_stub



def _resolve_storage_client(spec: str):
    """Resolve storage client from module path, e.g. dflow.plugins.bohrium.TiefblueClient."""
    if not spec or not isinstance(spec, str):
        return None
    try:
        module_path, _, cls_name = spec.rpartition(".")
        if not module_path or not cls_name:
            return None
        mod = importlib.import_module(module_path)
        cls = getattr(mod, cls_name)
        return cls()
    except Exception:
        return None


def _parse_repo_value(value: Any) -> Any:
    """Accept dict or JSON string for s3_repo / DFLOW_S3_REPO."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _apply_bohrium_config(
    dflow_section: Optional[Dict[str, Any]] = None,
    from_yaml: bool = False,
    from_env: bool = False,
) -> None:
    """设置 bohrium.config，供 TiefblueClient 初始化时读取。环境变量优先于 YAML。"""
    try:
        from dflow.plugins import bohrium
    except ImportError:
        return
    if from_yaml and dflow_section:
        if dflow_section.get("bohrium_username"):
            bohrium.config["username"] = str(dflow_section["bohrium_username"])
        if dflow_section.get("bohrium_password"):
            bohrium.config["password"] = str(dflow_section["bohrium_password"])
        if dflow_section.get("bohrium_project_id"):
            bohrium.config["project_id"] = str(dflow_section["bohrium_project_id"])
        if dflow_section.get("bohrium_access_key"):
            bohrium.config["access_key"] = str(dflow_section["bohrium_access_key"])
        if dflow_section.get("bohrium_app_key"):
            bohrium.config["app_key"] = str(dflow_section["bohrium_app_key"])
    if from_env:
        if os.getenv("BOHRIUM_USERNAME") is not None:
            bohrium.config["username"] = os.getenv("BOHRIUM_USERNAME", "")
        if os.getenv("BOHRIUM_PASSWORD") is not None:
            bohrium.config["password"] = os.getenv("BOHRIUM_PASSWORD", "")
        if os.getenv("BOHRIUM_PROJECT_ID") is not None:
            bohrium.config["project_id"] = os.getenv("BOHRIUM_PROJECT_ID", "")
        if os.getenv("BOHRIUM_ACCESS_KEY") is not None:
            bohrium.config["access_key"] = os.getenv("BOHRIUM_ACCESS_KEY", "")
        if os.getenv("BOHRIUM_APP_KEY") is not None:
            bohrium.config["app_key"] = os.getenv("BOHRIUM_APP_KEY", "")
        if os.getenv("BOHRIUM_TICKET") is not None:
            bohrium.config["ticket"] = os.getenv("BOHRIUM_TICKET", "")
        if os.getenv("BOHRIUM_AUTHORIZATION") is not None:
            bohrium.config["authorization"] = os.getenv("BOHRIUM_AUTHORIZATION", "")


def _exchange_bohrium_ticket(bohrium_plugin) -> Optional[str]:
    """Exchange access_key for a Brm-Ticket; return ticket or None.

    Older pydflow (e.g. 1.7) has no AccessKey/ticket support; then this no-ops
    unless the installed plugin exposes access_key + openapi_url.
    """
    access_key = (bohrium_plugin.config.get("access_key") or "").strip()
    if not access_key:
        return None
    # dflow 1.7 config has no openapi_url / ticket keys in the stock dict.
    openapi_url = (
        bohrium_plugin.config.get("openapi_url")
        or os.getenv("BOHRIUM_OPENAPI_URL")
        or "https://openapi.dp.tech"
    )
    import requests

    rsp = requests.get(
        openapi_url.rstrip("/") + "/openapi/v1/ticket/get",
        headers={"x-app-key": bohrium_plugin.config.get("app_key") or ""},
        params={"accessKey": access_key},
        timeout=60,
    )
    res = json.loads(rsp.text)
    if res.get("code") not in (0, "0000", 200, "200"):
        print(
            "[et-dflow debug] Bohrium ticket exchange failed: %s"
            % (res.get("error") or res.get("message") or res),
            flush=True,
        )
        return None
    ticket = (res.get("data") or {}).get("ticket")
    return str(ticket) if ticket else None


def _apply_bohrium_headers_to_dflow(bohrium_plugin) -> None:
    """Write Bohrium auth into ``dflow.config['http_headers']``.

    Compatible with pydflow 1.7 (no ``update_headers``) and newer releases.
    Replaces Cookie instead of appending, to avoid duplicated ``brmToken=``.
    """
    updater = getattr(bohrium_plugin, "update_headers", None)
    if callable(updater):
        updater()
        return

    headers = dflow_config.setdefault("http_headers", {})
    ticket = bohrium_plugin.config.get("ticket")
    authorization = bohrium_plugin.config.get("authorization")
    project_id = bohrium_plugin.config.get("project_id")

    # Never put ``Authorization: jwt ...`` on Argo http_headers: modern
    # update_headers() only sets Brm-Ticket or Cookie, and openresty on
    # workflows.deepmodeling.com often HTML-403s non-Bearer Authorization.
    auth = str(headers.get("Authorization") or "")
    if auth.lower().startswith("jwt "):
        headers.pop("Authorization", None)

    if ticket:
        headers["Brm-Ticket"] = str(ticket)
        # Prefer ticket over stale cookie when both exist.
        cookie = str(headers.get("Cookie") or "")
        if "brmToken=" in cookie:
            parts = [
                p.strip()
                for p in cookie.split(";")
                if p.strip() and not p.strip().startswith("brmToken=")
            ]
            if parts:
                headers["Cookie"] = "; ".join(parts)
            else:
                headers.pop("Cookie", None)
    elif authorization:
        headers["Cookie"] = "brmToken=" + str(authorization)

    if project_id:
        headers["Bohrium-Project-ID"] = str(project_id)


def _argo_auth_header_keys(headers: Optional[Dict[str, Any]] = None) -> Dict[str, bool]:
    headers = headers if headers is not None else (dflow_config.get("http_headers") or {})
    cookie = str(headers.get("Cookie") or "")
    auth = str(headers.get("Authorization") or "")
    return {
        "brm_ticket": bool(headers.get("Brm-Ticket")),
        "brm_cookie": "brmToken=" in cookie,
        "authorization_header": bool(auth.strip()),
        "project_id": bool(headers.get("Bohrium-Project-ID")),
    }


def _clear_empty_dflow_token() -> None:
    """Empty string must not become ``Authorization: Bearer `` on the Argo client."""
    raw = dflow_config.get("token")
    if raw is None:
        return
    if not str(raw).strip():
        dflow_config["token"] = None


def ensure_argo_auth_headers(*, require: bool = False) -> Dict[str, Any]:
    """Ensure Bohrium ticket/cookie (or DFLOW_TOKEN) is on Argo ``http_headers``.

    dflow ``create_job_group`` may obtain a ticket for its own POST without
    persisting ``bohrium.config["ticket"]``, so ``workflow.submit()`` would still
    hit openresty 403. Call this before submit.

    Also compatible with pydflow 1.7 which has ``login()`` + Cookie but no
    ``update_headers`` / AccessKey ticket helpers.
    """
    _clear_empty_dflow_token()
    token = (os.environ.get("DFLOW_TOKEN") or "").strip() or str(
        dflow_config.get("token") or ""
    ).strip()
    summary: Dict[str, Any] = {"token_len": len(token), "method": None}

    try:
        from dflow.plugins import bohrium as bohrium_plugin
    except ImportError:
        if require and not token:
            raise RuntimeError(
                "Argo submit needs DFLOW_TOKEN or Bohrium auth, but dflow.plugins.bohrium "
                "is unavailable."
            )
        return summary

    ticket_exchange_failed = False
    try:
        has_update_headers = callable(getattr(bohrium_plugin, "update_headers", None))
        summary["dflow_has_update_headers"] = has_update_headers

        if not bohrium_plugin.config.get("ticket"):
            access_key = (bohrium_plugin.config.get("access_key") or "").strip()
            if access_key:
                ticket = _exchange_bohrium_ticket(bohrium_plugin)
                if ticket:
                    bohrium_plugin.config["ticket"] = ticket
                    summary["method"] = "access_key_ticket"
                else:
                    ticket_exchange_failed = True
                    summary["ticket_exchange_failed"] = True

        have_user_pass = bool(
            bohrium_plugin.config.get("username")
            and bohrium_plugin.config.get("password")
        )
        if (
            not bohrium_plugin.config.get("ticket")
            and not bohrium_plugin.config.get("authorization")
            and have_user_pass
        ):
            bohrium_plugin.login()
            summary["method"] = "password_login"
        elif (
            not has_update_headers
            and not bohrium_plugin.config.get("ticket")
            and have_user_pass
            and "brmToken="
            not in str((dflow_config.get("http_headers") or {}).get("Cookie") or "")
        ):
            # pydflow 1.7: Cookie missing — re-login to populate brmToken.
            bohrium_plugin.config["authorization"] = None
            bohrium_plugin.login()
            summary["method"] = "password_login_refresh"

        _apply_bohrium_headers_to_dflow(bohrium_plugin)
        if summary["method"] is None:
            if bohrium_plugin.config.get("ticket"):
                summary["method"] = "existing_ticket"
            elif bohrium_plugin.config.get("authorization"):
                summary["method"] = "existing_authorization"
            elif bohrium_plugin.config.get("project_id"):
                summary["method"] = "project_id_only"
    except Exception as exc:
        print(
            "[et-dflow debug] Bohrium header setup skipped: %s" % exc,
            flush=True,
        )
        summary["error"] = str(exc)
        try:
            from dflow.plugins import bohrium as bohrium_plugin

            _apply_bohrium_headers_to_dflow(bohrium_plugin)
        except Exception:
            pass

    flags = _argo_auth_header_keys()
    summary["headers"] = flags
    print("[et-dflow debug] Argo auth headers:", summary, flush=True)

    host = str(dflow_config.get("host") or "")
    deepmodeling = "workflows.deepmodeling.com" in host
    has_ticket = flags["brm_ticket"]
    has_cookie = flags["brm_cookie"]

    if require and not token and deepmodeling and not has_ticket:
        # Gateway currently expects Brm-Ticket; JWT Cookie alone → openresty HTML 403.
        hint = (
            "Argo submit to workflows.deepmodeling.com needs Brm-Ticket "
            "(from a valid BOHRIUM_ACCESS_KEY), or DFLOW_TOKEN. "
            "Password/JWT Cookie can create Bohrium job groups but is rejected by "
            "the workflow gateway (openresty 403). "
            "Generate AccessKey at https://bohrium.dp.tech/settings/user then:\n"
            "  export BOHRIUM_ACCESS_KEY='...'\n"
            "  # optional: export BOHRIUM_APP_KEY='...'\n"
            "If the current AccessKey is invalid, unset it and set a new one."
        )
        if ticket_exchange_failed:
            raise RuntimeError(
                "BOHRIUM_ACCESS_KEY is invalid (ticket exchange failed). " + hint
            )
        raise RuntimeError(hint)

    has_bohr_auth = has_ticket or has_cookie or flags["authorization_header"]
    if require and not token and not has_bohr_auth:
        raise RuntimeError(
            "Argo workflow submit would get openresty 403: no DFLOW_TOKEN and no "
            "Bohrium Brm-Ticket/Cookie on dflow http_headers. "
            "Set BOHRIUM_ACCESS_KEY (https://bohrium.dp.tech/settings/user) "
            "or BOHRIUM_USERNAME/BOHRIUM_PASSWORD."
        )
    return summary


def _inject_http_headers_into_api_client(api_client: Any) -> None:
    """Copy dflow http_headers onto ApiClient.default_headers.

    argo ``call_api`` does ``header_params.update(self.default_headers)``, so
    putting Bohrium auth only in ``header_params`` can still lose to an empty
    ``Authorization: Bearer `` left on the client from Workflow.__init__.
    """
    headers = dflow_config.get("http_headers") or {}
    default = getattr(api_client, "default_headers", None)
    if not isinstance(default, dict):
        return
    # Drop empty Bearer that openresty rejects.
    auth = str(default.get("Authorization") or "")
    if auth.strip() in ("", "Bearer", "Bearer "):
        default.pop("Authorization", None)
    for key, value in headers.items():
        if value is None or value == "":
            continue
        if key == "Authorization" and str(value).lower().startswith("jwt "):
            continue
        if hasattr(api_client, "set_default_header"):
            api_client.set_default_header(key, str(value))
        else:
            default[key] = str(value)


def _preflight_argo_auth() -> None:
    """GET workflows list; raise a clear error on openresty HTML 403."""
    import requests

    host = str(dflow_config.get("host") or "").rstrip("/")
    namespace = str(dflow_config.get("namespace") or "argo")
    if not host:
        return
    url = f"{host}/api/v1/workflows/{namespace}"
    headers = dict(dflow_config.get("http_headers") or {})
    try:
        rsp = requests.get(url, headers=headers, timeout=30, verify=False)
    except Exception as exc:
        print(f"[et-dflow debug] Argo preflight request failed: {exc}", flush=True)
        return
    ctype = (rsp.headers.get("Content-Type") or "").lower()
    body_head = (rsp.text or "")[:180].replace("\n", " ")
    print(
        "[et-dflow debug] Argo preflight:",
        {
            "status": rsp.status_code,
            "content_type": ctype,
            "server": rsp.headers.get("Server"),
            "body_head": body_head,
        },
        flush=True,
    )
    if rsp.status_code == 403 and (
        "text/html" in ctype or "openresty" in body_head.lower() or "<html" in body_head.lower()
    ):
        raise RuntimeError(
            "Argo preflight GET returned openresty HTML 403 — workflow submit will fail "
            "the same way. http_headers now="
            f"{sorted(headers.keys())}. "
            "Fix BOHRIUM_ACCESS_KEY so Brm-Ticket is present "
            "(https://bohrium.dp.tech/settings/user), or set DFLOW_TOKEN. "
            "Confirm code is up to date: git log -1 should include "
            "'Brm-Ticket' / c6eeddd or newer."
        )


def refresh_workflow_argo_client(workflow: Any) -> None:
    """Rebuild Workflow Argo API client and inject Bohrium auth headers."""
    _clear_empty_dflow_token()
    summary = ensure_argo_auth_headers(require=True)
    _preflight_argo_auth()
    try:
        from argo.workflows.client import WorkflowServiceApi
        from dflow.workflow import get_argo_api_client
    except Exception as exc:
        print(
            f"[et-dflow debug] refresh Argo client skipped (import): {exc}",
            flush=True,
        )
        return
    token = dflow_config.get("token")
    if isinstance(token, str) and not token.strip():
        token = None
    workflow.token = token
    api_client = get_argo_api_client(getattr(workflow, "host", None), token)
    _inject_http_headers_into_api_client(api_client)
    workflow.api_instance = WorkflowServiceApi(api_client)
    print(
        "[et-dflow debug] refreshed Argo client:",
        {
            "token_is_none": token is None,
            "default_header_keys": sorted(
                getattr(api_client, "default_headers", {}).keys()
            ),
            "auth_summary": summary.get("headers"),
        },
        flush=True,
    )


def _attach_bohrium_http_headers() -> None:
    """Backward-compatible wrapper used by configure_dflow."""
    ensure_argo_auth_headers(require=False)


def _boolize(value: Any) -> bool:
    """Convert string/env style to bool for dflow options."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() not in ("", "false", "0")
    return bool(value)


def configure_dflow(
    dflow_section: Optional[Dict[str, Any]] = None,
    workflow_output_dir: Optional[str] = None,
    run_dir: Optional[Path] = None,
):
    """
    Configure dflow for remote cluster mode with settings from config manager,
    optional benchmark dflow section, and environment variables.

    Priority (highest last): ConfigManager settings < benchmark YAML `dflow`
    section < environment variables.

    Args:
        dflow_section: Optional dict from benchmark config (e.g. config["dflow"]).
            MinIO: host, namespace, k8s_api_server, mode, s3_endpoint, s3_bucket_name,
            s3_access_key, s3_secret_key, s3_secure, s3_console.
            Bohr (玻尔): host, namespace, k8s_api_server, token (empty), s3_repo_key
            (oss-bohrium), s3_repo / s3_repo_type (convert_to_argo stub; prefer
            ``oss: {}`` / ``oss``), s3_storage_client
            (dflow.plugins.bohrium.TiefblueClient), bohrium_username,
            bohrium_password, bohrium_project_id, bohrium_access_key,
            bohrium_app_key (prefer env BOHRIUM_ACCESS_KEY / BOHRIUM_APP_KEY;
            access_key exchanges a ticket without password).
        workflow_output_dir: Optional output dir from workflow config (e.g. config["workflow"]["output_dir"]).
        run_dir: Reserved for backward compatibility. Remote mode does not use local debug workdirs.
    """
    config_manager = get_config_manager()
    settings = config_manager.settings

    # 1) ConfigManager / Settings
    dflow_config["host"] = settings.dflow_host
    dflow_config["namespace"] = settings.dflow_namespace
    if settings.k8s_api_server:
        dflow_config["k8s_api_server"] = settings.k8s_api_server
    dflow_config["mode"] = "remote"

    # 2) Benchmark YAML dflow section (overrides settings)
    if dflow_section:
        if "host" in dflow_section:
            dflow_config["host"] = str(dflow_section["host"])
        if "namespace" in dflow_section:
            dflow_config["namespace"] = str(dflow_section["namespace"])
        if "k8s_api_server" in dflow_section and dflow_section["k8s_api_server"]:
            dflow_config["k8s_api_server"] = str(dflow_section["k8s_api_server"])
        if "mode" in dflow_section:
            dflow_config["mode"] = str(dflow_section["mode"])
        # Token: 仅从环境变量 DFLOW_TOKEN 读取，不从 YAML 写入 dflow_config，避免被序列化/日志带出并参与请求
        if dflow_section.get("token"):
            import warnings
            warnings.warn(
                "dflow.token in config file is ignored for security; set DFLOW_TOKEN environment variable instead.",
                UserWarning,
                stacklevel=2,
            )
        # S3 / MinIO from YAML (map to dflow s3_config keys)
        s3_updates = {}
        if "s3_endpoint" in dflow_section:
            s3_updates["endpoint"] = str(dflow_section["s3_endpoint"])
        if "s3_console" in dflow_section:
            s3_updates["console"] = str(dflow_section["s3_console"])
        if "s3_access_key" in dflow_section:
            s3_updates["access_key"] = str(dflow_section["s3_access_key"])
        if "s3_secret_key" in dflow_section:
            s3_updates["secret_key"] = str(dflow_section["s3_secret_key"])
        if "s3_secure" in dflow_section:
            s3_updates["secure"] = _boolize(dflow_section["s3_secure"])
        if "s3_bucket_name" in dflow_section:
            s3_updates["bucket_name"] = str(dflow_section["s3_bucket_name"])
        # Bohr/Tiefblue (玻尔空间站): 必须先设置 bohrium.config，再创建 TiefblueClient
        if "s3_repo_key" in dflow_section:
            s3_updates["repo_key"] = str(dflow_section["s3_repo_key"])
        if "s3_repo_type" in dflow_section:
            s3_updates["repo_type"] = str(dflow_section["s3_repo_type"])
        if "s3_repo" in dflow_section:
            s3_updates["repo"] = _parse_repo_value(dflow_section["s3_repo"])
        # 先设置 Bohrium 凭据（YAML + 环境变量覆盖），TiefblueClient() 初始化时会读取
        _apply_bohrium_config(dflow_section, from_yaml=True)
        _apply_bohrium_config(from_env=True)
        if "s3_storage_client" in dflow_section:
            client = _resolve_storage_client(str(dflow_section["s3_storage_client"]))
            if client is not None:
                s3_updates["storage_client"] = client
        if s3_updates:
            set_s3_config(**s3_updates)

    # 3) Environment variables (highest priority)
    if os.getenv("DFLOW_HOST"):
        dflow_config["host"] = os.getenv("DFLOW_HOST")
    if os.getenv("DFLOW_NAMESPACE"):
        dflow_config["namespace"] = os.getenv("DFLOW_NAMESPACE")
    k8s_env = os.getenv("DFLOW_K8S_API_SERVER") or os.getenv("K8S_API_SERVER")
    if k8s_env:
        dflow_config["k8s_api_server"] = k8s_env
    if os.getenv("DFLOW_MODE"):
        dflow_config["mode"] = os.getenv("DFLOW_MODE")
    # Token 仅从环境变量设置。空字符串必须变成 None：dflow get_argo_api_client
    # treats any non-None token as ``Authorization: Bearer ...``, and an empty
    # Bearer makes workflows.deepmodeling.com openresty return 403 even when
    # Bohrium Brm-Ticket is present on http_headers.
    raw_token = os.getenv("DFLOW_TOKEN", "") if "DFLOW_TOKEN" in os.environ else ""
    dflow_config["token"] = raw_token.strip() or None
    if os.getenv("DFLOW_S3_ENDPOINT"):
        set_s3_config(endpoint=os.getenv("DFLOW_S3_ENDPOINT"))
    if os.getenv("DFLOW_S3_CONSOLE"):
        set_s3_config(console=os.getenv("DFLOW_S3_CONSOLE"))
    if os.getenv("DFLOW_S3_ACCESS_KEY"):
        set_s3_config(access_key=os.getenv("DFLOW_S3_ACCESS_KEY"))
    if os.getenv("DFLOW_S3_SECRET_KEY"):
        set_s3_config(secret_key=os.getenv("DFLOW_S3_SECRET_KEY"))
    if os.getenv("DFLOW_S3_SECURE") is not None:
        set_s3_config(secure=_boolize(os.getenv("DFLOW_S3_SECURE")))
    if os.getenv("DFLOW_S3_BUCKET_NAME"):
        set_s3_config(bucket_name=os.getenv("DFLOW_S3_BUCKET_NAME"))
    # Bohr/Tiefblue
    if os.getenv("DFLOW_S3_REPO_KEY"):
        set_s3_config(repo_key=os.getenv("DFLOW_S3_REPO_KEY"))
    if os.getenv("DFLOW_S3_REPO_TYPE"):
        set_s3_config(repo_type=os.getenv("DFLOW_S3_REPO_TYPE"))
    if os.getenv("DFLOW_S3_REPO"):
        set_s3_config(repo=_parse_repo_value(os.getenv("DFLOW_S3_REPO")))
    _apply_bohrium_config(from_env=True)
    if os.getenv("DFLOW_S3_STORAGE_CLIENT"):
        client = _resolve_storage_client(os.getenv("DFLOW_S3_STORAGE_CLIENT"))
        if client is not None:
            set_s3_config(storage_client=client)

    # 3.5) Bohr 模式下清除 MinIO 默认值，避免连接 127.0.0.1:9000 / my-bucket
    use_bohr = (
        os.getenv("DFLOW_S3_REPO_KEY") == "oss-bohrium"
        or (dflow_section or {}).get("s3_repo_key") == "oss-bohrium"
        or os.getenv("BOHRIUM_USERNAME")
        or (dflow_section or {}).get("bohrium_username")
        or os.getenv("BOHRIUM_ACCESS_KEY")
        or (dflow_section or {}).get("bohrium_access_key")
        or (dflow_s3_config.get("repo_key") == "oss-bohrium")
        or (dflow_s3_config.get("storage_client") is not None)
    )
    if use_bohr:
        set_s3_config(endpoint=None, bucket_name=None)
        # Keep nested {"oss":{}} so convert_to_argo can assign loc["oss"]["key"].
        # Artifact I/O goes through TiefblueClient, not artifact-repositories.
        ensure_bohr_artifact_repo_stub()
        _attach_bohrium_http_headers()

    # Prefer https for the public workflow gateway.
    for key in ("host", "k8s_api_server"):
        if dflow_config.get(key) == "http://workflows.deepmodeling.com":
            dflow_config[key] = "https://workflows.deepmodeling.com"

    # [debug] 输出 dflow 配置的安全摘要，便于核对客户端是否正确设置了连接信息。
    # 不打印 token 内容，避免泄露；只打印 token 长度（0 表示未配置）。
    debug_view = {
        "host": dflow_config.get("host"),
        "namespace": dflow_config.get("namespace"),
        "mode": dflow_config.get("mode"),
        "k8s_api_server": dflow_config.get("k8s_api_server"),
        "token_len": len(dflow_config.get("token") or ""),
        "bohr": bool(use_bohr),
        "s3_repo_key": dflow_s3_config.get("repo_key"),
        "s3_repo_type": dflow_s3_config.get("repo_type"),
        "s3_repo": dflow_s3_config.get("repo"),
        "s3_repo_set": dflow_s3_config.get("repo") is not None,
    }
    print("[et-dflow debug] dflow_config summary:", debug_view)

    # 4) Remote cluster mode is the only supported runtime
    if str(dflow_config.get("mode", "remote")).lower() == "debug":
        raise ValueError(
            "Local/debug mode is no longer supported. "
            "Please configure dflow remote mode with Argo/Kubernetes and MinIO/S3."
        )

    required = {
        "host": dflow_config.get("host"),
        "namespace": dflow_config.get("namespace"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ValueError(
            f"Missing required remote dflow configuration: {', '.join(missing)}"
        )

    # S3/MinIO required only when not using Bohr backend
    if not use_bohr:
        missing_s3 = []
        if not (os.getenv("DFLOW_S3_ENDPOINT") or (dflow_section or {}).get("s3_endpoint")):
            missing_s3.append("s3_endpoint")
        if not (os.getenv("DFLOW_S3_BUCKET_NAME") or (dflow_section or {}).get("s3_bucket_name")):
            missing_s3.append("s3_bucket_name")
        if not (os.getenv("DFLOW_S3_ACCESS_KEY") or (dflow_section or {}).get("s3_access_key")):
            missing_s3.append("s3_access_key")
        if not (os.getenv("DFLOW_S3_SECRET_KEY") or (dflow_section or {}).get("s3_secret_key")):
            missing_s3.append("s3_secret_key")
        if missing_s3:
            raise ValueError(
                "Missing required remote S3/MinIO configuration: "
                + ", ".join(missing_s3)
            )
