"""
Setup script for ET-dflow Benchmark Framework.
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if not requirements_file.exists():
    raise FileNotFoundError(
        f"requirements.txt not found at {requirements_file}. "
        "Please ensure requirements.txt exists in the project root."
    )

requirements = []
optional_deps = []  # Dependencies that may not be available on all Python versions

if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Skip dflow - it's version-specific and may not be available
                if line.startswith("dflow") or line.startswith("pydflow"):
                    optional_deps.append(line)
                else:
                    requirements.append(line)

setup(
    name="et-dflow",
    version="0.1.0",
    description="A containerized, automated benchmark testing framework for material electron tomography",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="ET-dflow Contributors",
    author_email="your-email@example.com",
    url="https://github.com/your-org/ET-dflow",
    packages=find_packages(exclude=["tests", "tests.*", "docs", "docs.*"]),
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.2.0",
            "pytest-cov>=4.0.0",
            "pytest-mock>=3.10.0",
            "black>=22.10.0",
            "flake8>=5.0.0",
            "mypy>=0.991",
            "isort>=5.11.0",
        ],
        "docs": [
            "sphinx>=5.3.0",
            "sphinx-rtd-theme>=1.1.0",
        ],
        "dflow": optional_deps if optional_deps else ["dflow>=1.7.0"],  # Optional dflow dependency
    },
    entry_points={
        "console_scripts": [
            "et-dflow=et_dflow.application.cli.main:cli",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Topic :: Scientific/Engineering",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    keywords="electron tomography, benchmark, reconstruction, dflow, materials science",
)

