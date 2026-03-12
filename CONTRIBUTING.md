# Contributing to ET-dflow Benchmark Framework

Thank you for your interest in contributing to ET-dflow! This document provides guidelines and instructions for contributing.

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/yourusername/ET-dflow.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Run tests: `pytest tests/`
6. Submit a pull request

## Code Style

- Follow PEP 8 style guidelines
- Use type hints where appropriate
- Write docstrings for all public functions and classes
- Keep functions focused and small

## Testing

- Write tests for all new features
- Ensure all tests pass: `pytest tests/`
- Aim for high test coverage

## Documentation

- Update README.md if needed
- Add docstrings to new code
- Update API documentation if adding new APIs

## Adding Algorithms

1. Create algorithm class inheriting from `Algorithm`
2. Implement required methods
3. Create Dockerfile in `docker/algorithms/your_algorithm/`
4. Add to algorithm registry
5. Write tests

## Adding Datasets

1. Add dataset configuration to `configs/datasets.yaml`
2. Ensure data format is supported
3. Add metadata following EMDB standards
4. Document dataset in README

## Pull Request Process

1. Update CHANGELOG.md with your changes
2. Ensure all CI checks pass
3. Request review from maintainers
4. Address review comments

## Questions?

Open an issue or contact maintainers.

## Code of Conduct

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on constructive feedback

## Development Setup

### Prerequisites

- Python 3.8 or higher
- Git
- Docker (for algorithm containers)
- Kubernetes cluster (for dflow)

### Setup Steps

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/ET-dflow.git
   cd ET-dflow
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install dependencies:
   ```bash
   pip install -r requirements.txt
   pip install -e ".[dev]"
   ```

5. Install pre-commit hooks:
   ```bash
   pre-commit install
   ```

## Development Workflow

### Branch Strategy

- `main`: Stable, production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature branches
- `fix/*`: Bug fix branches

### Making Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes following the coding standards

3. Write tests for your changes

4. Ensure all tests pass:
   ```bash
   pytest
   ```

5. Run code quality checks:
   ```bash
   black et_dflow/
   isort et_dflow/
   flake8 et_dflow/
   mypy et_dflow/
   ```

6. Commit your changes:
   ```bash
   git add .
   git commit -m "Add: description of your changes"
   ```

7. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

8. Create a Pull Request

## Coding Standards

### Python Style

- Follow PEP 8
- Use Black for code formatting (line length: 100)
- Use isort for import sorting
- Type hints are encouraged but not required for all functions
- Maximum line length: 100 characters

### Code Organization

- Follow the layered architecture (core/domain/infrastructure/application)
- Use dependency injection for loose coupling
- Write docstrings for all public functions and classes
- Keep functions focused and small

### Documentation

- All code, comments, and docstrings must be in English
- Use Google-style docstrings
- Update documentation when adding features

### Testing

- Write unit tests for all new functionality
- Aim for >80% test coverage
- Use pytest fixtures for test data
- Mock external dependencies

## Adding New Algorithms

1. Create algorithm class inheriting from `Algorithm` base class
2. Implement required methods (`run`, `validate_input`, `get_requirements`)
3. Create Dockerfile in `docker/algorithms/your_algorithm/`
4. Add algorithm configuration to `configs/algorithms.yaml`
5. Write tests
6. Update documentation

## Adding New Datasets

1. Prepare dataset files
2. Add dataset configuration to `configs/datasets.yaml`
3. Ensure metadata follows EMDB standards
4. Write dataset loading tests
5. Update documentation

## Reporting Issues

When reporting issues, please include:

- Description of the problem
- Steps to reproduce
- Expected behavior
- Actual behavior
- Environment information (OS, Python version, etc.)
- Relevant logs or error messages

## Pull Request Process

1. Ensure your code follows the coding standards
2. All tests must pass
3. Code coverage should not decrease
4. Update documentation as needed
5. Add changelog entry if applicable
6. Request review from maintainers

## Questions?

Feel free to open an issue for questions or discussions.

Thank you for contributing!

