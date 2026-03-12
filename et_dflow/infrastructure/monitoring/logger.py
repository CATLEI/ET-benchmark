"""
Structured logging implementation.

Provides JSON-formatted structured logging.
"""

import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class StructuredLogger:
    """
    Structured logger with JSON output.
    
    Provides structured logging for better log analysis.
    """
    
    def __init__(
        self,
        name: str = "et_dflow",
        level: str = "INFO",
        output_path: Optional[str] = None
    ):
        """
        Initialize structured logger.
        
        Args:
            name: Logger name
            level: Log level
            output_path: Optional file path for logging
        """
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, level.upper()))
        
        # Create formatter
        self.formatter = StructuredFormatter()
        
        # Add console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(self.formatter)
        self.logger.addHandler(console_handler)
        
        # Add file handler if path provided
        if output_path:
            file_handler = logging.FileHandler(output_path)
            file_handler.setFormatter(self.formatter)
            self.logger.addHandler(file_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message with structured data."""
        self.logger.info(message, extra={"structured_data": kwargs})
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured data."""
        self.logger.warning(message, extra={"structured_data": kwargs})
    
    def error(self, message: str, **kwargs):
        """Log error message with structured data."""
        self.logger.error(message, extra={"structured_data": kwargs})
    
    def debug(self, message: str, **kwargs):
        """Log debug message with structured data."""
        self.logger.debug(message, extra={"structured_data": kwargs})


class StructuredFormatter(logging.Formatter):
    """JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        # Add structured data if present
        if hasattr(record, "structured_data"):
            log_data.update(record.structured_data)
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_data)

