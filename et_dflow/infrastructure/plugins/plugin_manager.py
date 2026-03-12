"""
Plugin management system.

Manages user extensions and plugins.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import importlib
import inspect
from et_dflow.core.exceptions import PluginError
from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.interfaces import IDataLoader, IAlgorithm


class PluginManager:
    """
    Plugin manager for user extensions.
    
    Discovers, loads, and validates plugins.
    """
    
    def __init__(self, plugin_dir: Optional[Path] = None):
        """
        Initialize plugin manager.
        
        Args:
            plugin_dir: Directory to search for plugins
        """
        self.plugin_dir = plugin_dir or Path("plugins")
        self.plugins: Dict[str, Dict[str, Any]] = {}
    
    def discover_plugins(self) -> List[str]:
        """
        Discover available plugins.
        
        Returns:
            List of plugin names
        """
        plugins = []
        
        if not self.plugin_dir.exists():
            return plugins
        
        # Search for plugin modules
        for plugin_file in self.plugin_dir.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            
            plugin_name = plugin_file.stem
            plugins.append(plugin_name)
        
        return plugins
    
    def load_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """
        Load plugin module.
        
        Args:
            plugin_name: Name of plugin
        
        Returns:
            Plugin metadata
        """
        try:
            # Import plugin module
            spec = importlib.util.spec_from_file_location(
                plugin_name,
                self.plugin_dir / f"{plugin_name}.py"
            )
            
            if spec is None or spec.loader is None:
                raise PluginError(f"Could not load plugin: {plugin_name}")
            
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Extract plugin metadata
            metadata = {
                "name": plugin_name,
                "version": getattr(module, "__version__", "1.0.0"),
                "algorithms": [],
                "loaders": [],
            }
            
            # Find algorithms and loaders
            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj):
                    if issubclass(obj, Algorithm) and obj != Algorithm:
                        metadata["algorithms"].append(name)
                    elif issubclass(obj, IDataLoader) and obj != IDataLoader:
                        metadata["loaders"].append(name)
            
            self.plugins[plugin_name] = metadata
            
            return metadata
            
        except Exception as e:
            raise PluginError(f"Failed to load plugin {plugin_name}: {e}") from e
    
    def validate_plugin(self, plugin_name: str) -> bool:
        """
        Validate plugin.
        
        Args:
            plugin_name: Name of plugin
        
        Returns:
            True if valid
        """
        if plugin_name not in self.plugins:
            return False
        
        # Check required metadata
        plugin = self.plugins[plugin_name]
        required_fields = ["name", "version"]
        
        for field in required_fields:
            if field not in plugin:
                return False
        
        return True
    
    def get_plugin(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get plugin metadata.
        
        Args:
            plugin_name: Name of plugin
        
        Returns:
            Plugin metadata or None
        """
        return self.plugins.get(plugin_name)

