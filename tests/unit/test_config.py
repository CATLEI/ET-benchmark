"""
Unit tests for configuration management.
"""

import pytest
import yaml
from pathlib import Path
import tempfile
import shutil
from et_dflow.core.config import ConfigManager, Settings, get_config_manager


class TestSettings:
    """Test Settings model."""
    
    def test_settings_creation(self):
        """Test settings can be created."""
        settings = Settings(
            docker_registry="test-registry",
            env="dev"
        )
        assert settings.env == "dev"
        assert settings.docker_registry == "test-registry"
    
    def test_settings_validation(self):
        """Test settings validation."""
        # Valid env
        settings = Settings(
            docker_registry="test",
            env="dev"
        )
        assert settings.env == "dev"
        
        # Invalid env should raise error
        with pytest.raises(ValueError):
            Settings(
                docker_registry="test",
                env="invalid"
            )


class TestConfigManager:
    """Test ConfigManager."""
    
    def test_config_manager_creation(self, temp_dir):
        """Test config manager can be created."""
        # Create minimal config files
        base_config = {
            "algorithms": {},
            "datasets": {}
        }
        
        base_file = temp_dir / "base.yaml"
        with open(base_file, "w") as f:
            yaml.dump(base_config, f)
        
        config_manager = ConfigManager(config_dir=temp_dir)
        assert config_manager is not None
    
    def test_get_config_value(self, temp_dir):
        """Test getting config value."""
        base_config = {
            "algorithms": {
                "wbp": {
                    "docker_image": "test/wbp:latest"
                }
            },
            "datasets": {}
        }
        
        base_file = temp_dir / "base.yaml"
        with open(base_file, "w") as f:
            yaml.dump(base_config, f)
        
        config_manager = ConfigManager(config_dir=temp_dir)
        docker_image = config_manager.get("algorithms.wbp.docker_image")
        assert docker_image == "test/wbp:latest"
    
    def test_get_section(self, temp_dir):
        """Test getting config section."""
        base_config = {
            "algorithms": {
                "wbp": {"docker_image": "test/wbp:latest"}
            },
            "datasets": {}
        }
        
        base_file = temp_dir / "base.yaml"
        with open(base_file, "w") as f:
            yaml.dump(base_config, f)
        
        config_manager = ConfigManager(config_dir=temp_dir)
        algorithms = config_manager.get_section("algorithms")
        assert "wbp" in algorithms

