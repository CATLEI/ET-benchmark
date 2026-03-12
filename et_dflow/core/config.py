"""
Configuration management for ET-dflow Benchmark Framework.

Provides centralized configuration management with support for
environment-based configs, validation, and secret management.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    from pydantic import field_validator
    PYDANTIC_V2 = True
    # For pydantic v2, use Field without env parameter, use model_config instead
    from pydantic import Field as PydanticField
    def Field(*args, env=None, **kwargs):
        # Store env in kwargs for later use
        if env:
            kwargs['_env'] = env
        return PydanticField(*args, **kwargs)
except ImportError:
    # Fallback for older pydantic versions
    from pydantic import BaseSettings, Field, validator
    PYDANTIC_V2 = False
from et_dflow.core.exceptions import ConfigurationError


class Settings(BaseSettings):
    """
    Application settings with validation.
    
    Uses Pydantic for validation and environment variable support.
    """
    
    # Environment
    env: str = Field(default="dev", env="ENVIRONMENT")
    
    # Docker settings
    docker_registry: str = Field(default="localhost", env="DOCKER_REGISTRY")
    docker_username: Optional[str] = Field(default=None, env="DOCKER_USERNAME")
    docker_password: Optional[str] = Field(default=None, env="DOCKER_PASSWORD")
    
    # dflow settings
    dflow_host: str = Field(default="http://localhost:2746", env="DFLOW_HOST")
    dflow_namespace: str = Field(default="default", env="DFLOW_NAMESPACE")
    k8s_api_server: Optional[str] = Field(default=None, env="K8S_API_SERVER")
    
    # Resource settings
    default_cpu: int = Field(default=2, env="DEFAULT_CPU")
    default_memory: str = Field(default="4Gi", env="DEFAULT_MEMORY")
    default_gpu: int = Field(default=0, env="DEFAULT_GPU")
    
    # Storage settings
    cache_dir: Path = Field(default=Path(".cache"), env="CACHE_DIR")
    output_dir: Path = Field(default=Path("./output"), env="OUTPUT_DIR")
    
    # Logging settings
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="json", env="LOG_FORMAT")  # 'json' or 'text'
    
    # Monitoring settings
    metrics_port: int = Field(default=8000, env="METRICS_PORT")
    
    if PYDANTIC_V2:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
            env_prefix="",  # No prefix
            env_nested_delimiter="__"
        )
        
        @field_validator("env")
        @classmethod
        def validate_env(cls, v):
            """Validate environment value."""
            allowed = ["dev", "test", "prod"]
            if v not in allowed:
                raise ValueError(f"env must be one of {allowed}")
            return v
        
        @field_validator("log_level")
        @classmethod
        def validate_log_level(cls, v):
            """Validate log level."""
            allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v.upper() not in allowed:
                raise ValueError(f"log_level must be one of {allowed}")
            return v.upper()
    else:
        @validator("env")
        def validate_env(cls, v):
            """Validate environment value."""
            allowed = ["dev", "test", "prod"]
            if v not in allowed:
                raise ValueError(f"env must be one of {allowed}")
            return v
        
        @validator("log_level")
        def validate_log_level(cls, v):
            """Validate log level."""
            allowed = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
            if v.upper() not in allowed:
                raise ValueError(f"log_level must be one of {allowed}")
            return v.upper()
        
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False


class ConfigManager:
    """
    Centralized configuration management.
    
    Features:
    - Environment-based config (dev/test/prod)
    - Config validation
    - Secret management
    - Config merging
    
    Example:
        config_manager = ConfigManager(env="dev")
        dataset_config = config_manager.get("datasets.simulated_xct")
    """
    
    def __init__(self, env: Optional[str] = None, config_dir: Optional[Path] = None):
        """
        Initialize configuration manager.
        
        Args:
            env: Environment name ('dev', 'test', 'prod')
            config_dir: Directory containing config files (default: 'configs')
        """
        self.settings = Settings()
        self.env = env or self.settings.env
        self.config_dir = config_dir or Path("configs")
        self.config: Dict[str, Any] = {}
        self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load and merge configuration files.
        
        Priority: user > env > base
        
        Returns:
            Merged configuration dictionary
        """
        # Load base config
        base_config = self._load_yaml("base.yaml", required=True)
        
        # Load environment-specific config
        env_config = self._load_yaml(f"{self.env}.yaml", required=False)
        
        # Load user config (optional, for local overrides)
        user_config = self._load_yaml("user.yaml", required=False)
        
        # Merge configs with priority: user > env > base
        self.config = self._merge_configs(base_config, env_config, user_config)
        
        # Validate config
        self._validate_config()
        
        # Inject secrets from environment
        self.config = self._inject_secrets(self.config)
        
        return self.config
    
    def _load_yaml(self, filename: str, required: bool = True) -> Dict[str, Any]:
        """
        Load YAML configuration file.
        
        Args:
            filename: Configuration file name
            required: Whether file is required
        
        Returns:
            Configuration dictionary
        
        Raises:
            ConfigurationError: If required file is missing
        """
        file_path = self.config_dir / filename
        
        if not file_path.exists():
            if required:
                raise ConfigurationError(
                    f"Required config file not found: {file_path}",
                    details={"file": str(file_path)}
                )
            return {}
        
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
            return config
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Error parsing config file {file_path}: {e}",
                details={"file": str(file_path), "error": str(e)}
            )
    
    def _merge_configs(self, *configs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge multiple configuration dictionaries.
        
        Later configs override earlier ones.
        
        Args:
            *configs: Configuration dictionaries to merge
        
        Returns:
            Merged configuration dictionary
        """
        merged = {}
        for config in configs:
            merged = self._deep_merge(merged, config)
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> Dict[str, Any]:
        """
        Deep merge two dictionaries.
        
        Args:
            base: Base dictionary
            update: Dictionary to merge into base
        
        Returns:
            Merged dictionary
        """
        result = base.copy()
        
        for key, value in update.items():
            if (
                key in result and
                isinstance(result[key], dict) and
                isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _validate_config(self):
        """
        Validate configuration.
        
        Checks for required fields and valid values.
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        # Validate required top-level sections
        required_sections = ["algorithms", "datasets"]
        for section in required_sections:
            if section not in self.config:
                raise ConfigurationError(
                    f"Missing required config section: {section}",
                    details={"section": section}
                )
        
        # Validate algorithm configs
        algorithms = self.config.get("algorithms", {})
        for alg_name, alg_config in algorithms.items():
            if not isinstance(alg_config, dict):
                raise ConfigurationError(
                    f"Invalid algorithm config for {alg_name}",
                    details={"algorithm": alg_name}
                )
            if "docker_image" not in alg_config:
                raise ConfigurationError(
                    f"Algorithm {alg_name} missing docker_image",
                    details={"algorithm": alg_name}
                )
    
    def _inject_secrets(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inject secrets from environment variables.
        
        Replaces placeholders like ${VAR_NAME} with environment variable values.
        
        Args:
            config: Configuration dictionary
        
        Returns:
            Configuration with secrets injected
        """
        import re
        
        def replace_secrets(obj: Any) -> Any:
            """Recursively replace secret placeholders."""
            if isinstance(obj, dict):
                return {k: replace_secrets(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_secrets(item) for item in obj]
            elif isinstance(obj, str):
                # Replace ${VAR_NAME} with environment variable
                pattern = r'\$\{([^}]+)\}'
                matches = re.findall(pattern, obj)
                for var_name in matches:
                    env_value = os.getenv(var_name)
                    if env_value:
                        obj = obj.replace(f"${{{var_name}}}", env_value)
                return obj
            return obj
        
        return replace_secrets(config)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.
        
        Args:
            key: Configuration key (e.g., 'algorithms.wbp.docker_image')
            default: Default value if key not found
        
        Returns:
            Configuration value
        
        Example:
            docker_image = config_manager.get('algorithms.wbp.docker_image')
        """
        keys = key.split(".")
        value = self.config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_section(self, section: str) -> Dict[str, Any]:
        """
        Get entire configuration section.
        
        Args:
            section: Section name (e.g., 'algorithms', 'datasets')
        
        Returns:
            Configuration section dictionary
        
        Raises:
            ConfigurationError: If section not found
        """
        if section not in self.config:
            raise ConfigurationError(
                f"Configuration section not found: {section}",
                details={"section": section}
            )
        return self.config[section]
    
    def reload(self):
        """Reload configuration from files."""
        self._load_config()


# Global config manager instance
_config_manager: Optional[ConfigManager] = None


def get_config_manager(env: Optional[str] = None) -> ConfigManager:
    """
    Get global configuration manager.
    
    Args:
        env: Environment name (optional)
    
    Returns:
        Global ConfigManager instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager(env=env)
    return _config_manager


def set_config_manager(config_manager: ConfigManager):
    """
    Set global configuration manager.
    
    Args:
        config_manager: ConfigManager instance to use as global manager
    """
    global _config_manager
    _config_manager = config_manager

