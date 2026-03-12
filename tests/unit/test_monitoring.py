"""
Unit tests for monitoring system.
"""

import pytest
from et_dflow.infrastructure.monitoring.metrics_collector import MetricsCollector
from et_dflow.infrastructure.monitoring.logger import StructuredLogger
from et_dflow.infrastructure.monitoring.tracer import WorkflowTracer


class TestMetricsCollector:
    """Test MetricsCollector."""
    
    def test_collector_creation(self):
        """Test collector can be created."""
        collector = MetricsCollector()
        assert collector is not None
    
    def test_increment_counter(self):
        """Test counter increment."""
        collector = MetricsCollector()
        collector.increment_counter("test_counter")
        collector.increment_counter("test_counter")
        
        metrics = collector.get_metrics()
        assert metrics["counters"]["test_counter"] == 2
    
    def test_set_gauge(self):
        """Test gauge setting."""
        collector = MetricsCollector()
        collector.set_gauge("test_gauge", 42.5)
        
        metrics = collector.get_metrics()
        assert metrics["gauges"]["test_gauge"] == 42.5
    
    def test_observe_histogram(self):
        """Test histogram observation."""
        collector = MetricsCollector()
        collector.observe_histogram("test_hist", 1.0)
        collector.observe_histogram("test_hist", 2.0)
        collector.observe_histogram("test_hist", 3.0)
        
        metrics = collector.get_metrics()
        hist = metrics["histograms"]["test_hist"]
        assert hist["count"] == 3
        assert hist["mean"] == 2.0
    
    def test_record_execution_time(self):
        """Test execution time recording."""
        collector = MetricsCollector()
        collector.record_execution_time("test_op", 1.5)
        
        metrics = collector.get_metrics()
        assert "test_op_duration_seconds" in metrics["histograms"]


class TestStructuredLogger:
    """Test StructuredLogger."""
    
    def test_logger_creation(self):
        """Test logger can be created."""
        logger = StructuredLogger()
        assert logger is not None
    
    def test_logging(self):
        """Test logging methods."""
        logger = StructuredLogger()
        
        # Should not raise exceptions
        logger.info("Test message", key="value")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.debug("Debug message")


class TestWorkflowTracer:
    """Test WorkflowTracer."""
    
    def test_tracer_creation(self):
        """Test tracer can be created."""
        tracer = WorkflowTracer()
        assert tracer is not None
    
    def test_trace_workflow(self):
        """Test workflow tracing."""
        tracer = WorkflowTracer()
        
        trace_id = tracer.start_trace("test_workflow")
        assert trace_id is not None
        
        tracer.add_step("step1", metadata={"key": "value"})
        tracer.add_step("step2")
        
        tracer.finish_trace(status="completed")
        
        trace = tracer.get_trace(trace_id)
        assert trace is not None
        assert trace["workflow_name"] == "test_workflow"
        assert len(trace["steps"]) == 2
        assert trace["status"] == "completed"

