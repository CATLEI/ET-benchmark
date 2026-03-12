"""
dflow configuration.

Configures dflow connection and S3/storage for remote cluster mode.
"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

from dflow import config as dflow_config, set_s3_config
from et_dflow.core.config import get_config_manager


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
            May contain: host, namespace, k8s_api_server, mode, s3_endpoint,
            s3_bucket_name, s3_access_key, s3_secret_key, s3_secure, s3_console.
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
        if s3_updates:
            set_s3_config(**s3_updates)

    # 3) Environment variables (highest priority)
    if os.getenv("DFLOW_HOST"):
        dflow_config["host"] = os.getenv("DFLOW_HOST")
    if os.getenv("DFLOW_NAMESPACE"):
        dflow_config["namespace"] = os.getenv("DFLOW_NAMESPACE")
    if os.getenv("K8S_API_SERVER"):
        dflow_config["k8s_api_server"] = os.getenv("K8S_API_SERVER")
    if os.getenv("DFLOW_MODE"):
        dflow_config["mode"] = os.getenv("DFLOW_MODE")
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
