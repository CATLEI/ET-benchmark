"""
dflow configuration.

Configures dflow connection and S3/storage for remote cluster mode.
Supports MinIO (self-hosted) and Bohr/Tiefblue (玻尔空间站) backends.
"""

import importlib
import os
from pathlib import Path
from typing import Any, Dict, Optional

from dflow import config as dflow_config, s3_config as dflow_s3_config, set_s3_config
from et_dflow.core.config import get_config_manager


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
    if from_env:
        if os.getenv("BOHRIUM_USERNAME") is not None:
            bohrium.config["username"] = os.getenv("BOHRIUM_USERNAME", "")
        if os.getenv("BOHRIUM_PASSWORD") is not None:
            bohrium.config["password"] = os.getenv("BOHRIUM_PASSWORD", "")
        if os.getenv("BOHRIUM_PROJECT_ID") is not None:
            bohrium.config["project_id"] = os.getenv("BOHRIUM_PROJECT_ID", "")


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
            (oss-bohrium), s3_storage_client (dflow.plugins.bohrium.TiefblueClient),
            bohrium_username, bohrium_password, bohrium_project_id.
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
    # Token 仅从环境变量设置，避免进入配置文件或序列化
    if "DFLOW_TOKEN" in os.environ:
        dflow_config["token"] = os.getenv("DFLOW_TOKEN", "")
    else:
        dflow_config["token"] = ""
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
        or (dflow_s3_config.get("repo_key") == "oss-bohrium")
        or (dflow_s3_config.get("storage_client") is not None)
    )
    if use_bohr:
        set_s3_config(endpoint=None, bucket_name=None)

    # [debug] 输出 dflow 配置的安全摘要，便于核对客户端是否正确设置了连接信息。
    # 不打印 token 内容，避免泄露；只打印 token 长度（0 表示未配置）。
    debug_view = {
        "host": dflow_config.get("host"),
        "namespace": dflow_config.get("namespace"),
        "mode": dflow_config.get("mode"),
        "k8s_api_server": dflow_config.get("k8s_api_server"),
        "token_len": len(dflow_config.get("token") or ""),
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
