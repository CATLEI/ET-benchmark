"""
Command-line interface for ET-dflow Benchmark Framework.

Provides CLI commands for running benchmarks and managing workflows.
"""

import click
import yaml
import json
from pathlib import Path
from typing import Optional
from et_dflow.infrastructure.utils.config_wizard import ConfigWizard, SimpleMode, ConfigValidator
from et_dflow.core.exceptions import ConfigurationError


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """ET-dflow Benchmark Framework CLI."""
    pass


@cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--output-dir", default="./results", help="Output directory")
@click.option("--verbose", is_flag=True, help="Verbose output")
@click.option("--dflow-host", default=None, help="dflow server host (overrides config)")
@click.option("--dflow-namespace", default=None, help="dflow namespace (overrides config)")
@click.option("--skip-image-validation", is_flag=True, help="Skip Docker image validation (not recommended)")
def benchmark(config_file: str, output_dir: str, verbose: bool, dflow_host: str, dflow_namespace: str, skip_image_validation: bool):
    """
    Run benchmark evaluation.
    
    CONFIG_FILE: Path to configuration file
    """
    click.echo(f"Running benchmark with config: {config_file}")
    click.echo(f"Output directory: {output_dir}")
    
    # Load configuration
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        raise click.Abort()

    config.setdefault("workflow", {})
    config["workflow"]["output_dir"] = output_dir
    
    # Validate configuration
    validator = ConfigValidator()
    validation_result = validator.validate(config)
    
    if not validation_result["valid"]:
        click.echo("Configuration validation failed:", err=True)
        for error in validation_result["errors"]:
            click.echo(f"  Error: {error}", err=True)
        raise click.Abort()
    
    if validation_result["warnings"]:
        click.echo("Configuration warnings:")
        for warning in validation_result["warnings"]:
            click.echo(f"  Warning: {warning}")
    
    # Validate that algorithms have docker_image specified
    algorithms = config.get("algorithms", {})
    if not algorithms:
        click.echo("Error: No algorithms found in configuration", err=True)
        raise click.Abort()
    
    for alg_name, alg_config in algorithms.items():
        if alg_config.get("enabled", True) and not alg_config.get("docker_image"):
            click.echo(f"Error: Algorithm {alg_name} missing required 'docker_image' field", err=True)
            click.echo("  All algorithms must specify a docker_image for dflow execution", err=True)
            raise click.Abort()
    
    dflow_section = config.get("dflow", {})
    is_remote_mode = str(dflow_section.get("mode", "remote")).lower() != "debug"

    # Validate Docker images (if not skipped). In remote cluster mode, skip local Docker validation.
    if not skip_image_validation and not is_remote_mode:
        click.echo("\nValidating Docker images...")
        try:
            from et_dflow.infrastructure.utils.docker_validator import DockerImageValidator
            
            # Get docker config from config file
            docker_config = config.get("docker", {})
            validate_images = docker_config.get("validate_images", True)
            pull_if_missing = docker_config.get("pre_pull", True)
            validation_timeout = docker_config.get("validation_timeout", 30)
            
            if validate_images:
                validator = DockerImageValidator(
                    timeout=validation_timeout,
                    pull_if_missing=pull_if_missing
                )
                
                validation_failed = False
                for alg_name, alg_config in algorithms.items():
                    if not alg_config.get("enabled", True):
                        continue
                    
                    docker_image = alg_config.get("docker_image")
                    if not docker_image:
                        continue
                    
                    click.echo(f"  Validating image for {alg_name}: {docker_image}...", nl=False)
                    is_valid, error = validator.validate_image(docker_image, pull_if_missing)
                    
                    if is_valid:
                        click.echo(" [OK]")
                    else:
                        click.echo(" [FAILED]")
                        click.echo(f"    Error: {error}", err=True)
                        validation_failed = True
                
                if validation_failed:
                    click.echo("\nDocker image validation failed. Please ensure:", err=True)
                    click.echo("  1. Docker is installed and running", err=True)
                    click.echo("  2. Images are available locally or can be pulled from registry", err=True)
                    click.echo("  3. You have permission to run Docker commands", err=True)
                    click.echo("\nTo skip validation (not recommended), use --skip-image-validation", err=True)
                    raise click.Abort()
                else:
                    click.echo("[OK] All Docker images validated successfully\n")
            else:
                click.echo("  Image validation disabled in configuration")
        except ImportError as e:
            click.echo(f"Warning: Could not import Docker validator: {e}", err=True)
            click.echo("  Continuing without image validation...", err=True)
        except Exception as e:
            click.echo(f"Error during image validation: {e}", err=True)
            if verbose:
                import traceback
                traceback.print_exc()
            raise click.Abort()
    elif skip_image_validation:
        click.echo("Skipping Docker image validation (--skip-image-validation flag set)")
    else:
        click.echo("Skipping local Docker image validation in remote cluster mode")
    
    # Run benchmark using dflow workflow
    click.echo("Benchmark execution started (using dflow workflow)...")
    try:
        from et_dflow.infrastructure.workflows.baseline_workflow import BaselineBenchmarkWorkflow
        import os
        
        # Configure dflow if host/namespace provided
        if dflow_host:
            os.environ["DFLOW_HOST"] = dflow_host
        if dflow_namespace:
            os.environ["DFLOW_NAMESPACE"] = dflow_namespace
        
        # Create and submit workflow
        workflow = BaselineBenchmarkWorkflow(config)
        workflow_id = workflow.submit()
        workflow_ids = workflow_id if isinstance(workflow_id, list) else [workflow_id]

        click.echo(f"[OK] Workflow(s) submitted ({len(workflow_ids)}): {', '.join(workflow_ids)}")
        for wid in workflow_ids:
            click.echo(f"  Monitor: dflow workflow get {wid}")
            click.echo(f"  Wait: dflow workflow wait {wid}")
        if click.confirm("Wait for workflow completion?", default=False):
            names = workflow.enabled_algorithm_names
            if names:
                click.echo(
                    "Waiting for workflow(s) to complete "
                    f"({len(names)} algorithm row(s): {', '.join(names)})..."
                )
            else:
                click.echo("Waiting for workflow(s) to complete...")
            local_results_dirs = []
            for wid in workflow_ids:
                workflow.wait(wid)
                status = workflow.get_status(wid)
                click.echo(f"Workflow {wid} status: {status}")
                local_results_dirs.append(workflow.download_results(wid))
            click.echo(f"Results downloaded to: {', '.join(str(p) for p in local_results_dirs)}")
        
    except ImportError as e:
        click.echo(f"Error: dflow not available - {e}", err=True)
        click.echo("Install dflow: pip install dflow>=1.7.0 kubernetes>=24.0.0", err=True)
        raise click.Abort()
    except Exception as e:
        import traceback
        click.echo(f"Error submitting dflow workflow: {type(e).__name__}: {e}", err=True)
        click.echo("Full traceback:", err=True)
        traceback.print_exc()
        raise click.Abort()


@cli.command()
@click.argument("config_file", type=click.Path(exists=False))
def validate(config_file: str):
    """
    Validate configuration file.
    
    CONFIG_FILE: Path to configuration file
    """
    if not Path(config_file).exists():
        click.echo(f"Configuration file not found: {config_file}", err=True)
        raise click.Abort()
    
    # Load configuration
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        raise click.Abort()
    
    # Validate
    validator = ConfigValidator()
    result = validator.validate(config)
    
    if result["valid"]:
        click.echo("[OK] Configuration is valid")
    else:
        click.echo("[FAILED] Configuration validation failed:", err=True)
        for error in result["errors"]:
            click.echo(f"  Error: {error}", err=True)
        raise click.Abort()
    
    if result["warnings"]:
        click.echo("\nWarnings:")
        for warning in result["warnings"]:
            click.echo(f"  Warning: {warning}")
    
    if result["suggestions"]:
        click.echo("\nSuggestions:")
        for suggestion in result["suggestions"]:
            click.echo(f"  Suggestion: {suggestion}")


@cli.command()
@click.option("--output", default="config.yaml", help="Output configuration file")
def init(output: str):
    """Initialize configuration file."""
    click.echo(f"Creating configuration file: {output}")
    
    wizard = ConfigWizard()
    config = wizard.create_config(output_path=output)
    
    click.echo(f"[OK] Configuration file created: {output}")


@cli.command()
@click.argument("dataset_path", type=click.Path(exists=True))
@click.option("--algorithm", default="wbp", help="Algorithm to use")
@click.option("--output", default="simple_config.yaml", help="Output configuration file")
def quick_start(dataset_path: str, algorithm: str, output: str):
    """Quick start with minimal configuration."""
    click.echo(f"Creating simple configuration for dataset: {dataset_path}")
    
    config = SimpleMode.create_simple_config(
        dataset_path=dataset_path,
        algorithm=algorithm,
        output_dir="./results"
    )
    
    # Save configuration
    with open(output, "w") as f:
        yaml.dump(config, f, default_flow_style=False)
    
    click.echo(f"[OK] Simple configuration created: {output}")


if __name__ == "__main__":
    cli()

