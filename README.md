# ET-dflow Benchmark Framework

A containerized, automated benchmark testing framework for material electron tomography (ET) reconstruction and evaluation.

## Features

- **Automated Reconstruction**: Run multiple reconstruction algorithms on datasets
- **Comprehensive Evaluation**: Evaluate algorithms using ET-specific metrics (FSC, directional resolution, atomic accuracy, etc.)
- **Remote Cluster Execution**: Submit workflows from a master node and run steps on Kubernetes/Argo workers
- **Missing Wedge Analysis**: Systematic investigation of missing wedge effects
- **Publication-Quality Visualization**: Scientific plotting with colorblind-friendly palettes
- **User Extensible**: Easy to add custom algorithms and datasets
- **Format Conversion**: Automatic format detection and conversion (MRC, TIFF → Hyperspy)
- **Multi-Format Output**: Save results in both `.hspy` (Hyperspy/ETSpy compatible) and `.npy` (pure array) formats
- **Artifact-Based Transfer**: Use MinIO/S3-backed dflow artifacts to move prepared data, reconstructions, and metrics between steps

Algorithm Docker images (WBP/SIRT production vs adapter placeholders, `placeholder_backend`, metadata) are documented in **[docs/ALGORITHMS_DOCKER.md](docs/ALGORITHMS_DOCKER.md)**.

## Installation

### Python版本要求

- **Python 3.8+**（推荐 3.10+）: 使用 `requirements.txt`。`setup.py` 声明 `python_requires=">=3.8"`。

### 安装步骤

**Python 3.8+（推荐 3.10）**:
```bash
# Clone repository
git clone https://github.com/yourusername/ET-dflow.git
cd ET-dflow

# Create conda environment
conda create -n etdflow python=3.10
conda activate etdflow

# Install dependencies (Python 3.10 compatible)
pip install -r requirements.txt

# Install package
pip install -e .
```

**注意**: 若 dflow 安装失败，可尝试 `pip install dflow>=1.7.0 kubernetes>=24.0.0`（参见 requirements 中的可选依赖）。

## Quick Start

### Remote and Hybrid Modes

- **Remote mode**: All steps (data prep, algorithm, evaluation, comparison, export) run in remote containers. Requires `workflow.runner_image` and algorithm `docker_image`.
- **Hybrid mode**: Set `workflow.execution_mode: "hybrid"`. Data preparation and evaluation run on the master node; only the algorithm step runs in a remote container. **No `runner_image` needed** — only the algorithm image (e.g. WBP) must be in a cluster-accessible registry. Use `configs/wbp_hybrid_benchmark.yaml` as a template.

Minimal benchmark config:

```yaml
datasets:
  my_dataset:
    path: "./data/datasets/tomo_01/raw/tilt_series.mrc"
    format: "mrc"
    ground_truth_path: "./data/datasets/tomo_01/raw/ground_truth.hspy"

algorithms:
  wbp:
    enabled: true
    docker_image: "registry.example.com/et-dflow/wbp:latest"
    parameters:
      filter_type: "ramp"

evaluation:
  metrics: ["psnr", "ssim", "mse"]

workflow:
  name: "tomo-01-benchmark"
  type: "baseline_benchmark"
  output_dir: "./results"
  # Omit runner_image when using execution_mode: "hybrid"
  runner_image: "registry.example.com/et-dflow/runner:latest"

dflow:
  mode: "remote"
  host: "https://argo.example.com"
  namespace: "argo"
  k8s_api_server: "https://kubernetes.default.svc"
  s3_endpoint: "http://minio.example.com:9000"
  s3_bucket_name: "et-dflow"
  s3_access_key: "minioadmin"
  s3_secret_key: "minioadmin"
  s3_secure: false
```

Run:

```bash
et-dflow benchmark config.yaml --output-dir ./results
```

After the workflow completes, the CLI downloads and unpacks results to:

```text
results/<time>/
├── data/
│   ├── prepared_data.hspy
│   └── prepared_data_ground_truth.hspy   # if provided
├── wbp/
│   ├── reconstruction.hspy
│   ├── reconstruction.npy
│   └── evaluation.json
├── comparison_summary.json
└── comparison_report.html
```

### Simple Mode Config Generation

```bash
# Create simple configuration (writes simple_config.yaml by default)
et-dflow quick-start ./data/my_dataset.hspy --algorithm wbp

# Run benchmark using the generated config
et-dflow benchmark simple_config.yaml
```

To use a different config filename: `et-dflow quick-start ./data/my_dataset.hspy --output config.yaml`, then edit the generated file to add the remote `dflow` section and run `et-dflow benchmark config.yaml`.

Benchmark execution is driven by the CLI. For programmatic config creation, you can use `SimpleMode` from the config wizard (see [Configuration](docs/CONFIGURATION_GUIDE.md)); run the benchmark with `et-dflow benchmark <path_to_config.yaml>`. Remote cluster mode requires a reachable Argo/dflow endpoint and S3/MinIO artifact storage—see [dflow and S3/MinIO](docs/CONFIGURATION_GUIDE.md#dflow-与-s3minio) in the configuration guide.

## Architecture

### 分层架构设计

ET-dflow采用分层架构（Layered Architecture），将系统分为四个主要层次：

```
┌─────────────────────────────────────────┐
│     Application Layer                   │
│  (CLI, Workflow Orchestration)          │
├─────────────────────────────────────────┤
│     Infrastructure Layer                 │
│  (Data Loading, Workflows, Monitoring)  │
├─────────────────────────────────────────┤
│     Domain Layer                        │
│  (Algorithms, Evaluation Logic)         │
├─────────────────────────────────────────┤
│     Core Layer                          │
│  (Interfaces, Models, Exceptions)       │
└─────────────────────────────────────────┘
```

#### 1. Core Layer (`et_dflow/core/`)

**职责**: 定义核心接口、数据模型和异常处理

- **Interfaces** (`interfaces.py`): 定义所有核心接口
  - `IDataLoader`: 数据加载接口
  - `IAlgorithm`: 算法执行接口
  - `IEvaluator`: 评估指标接口
  - `IPreprocessor`: 数据预处理接口

- **Models** (`models.py`): 数据模型
  - `AlgorithmResult`: 算法执行结果
  - `EvaluationResult`: 评估结果
  - `Dataset`: 数据集模型

- **Exceptions** (`exceptions.py`): 统一异常处理
  - `ETDflowError`: 基础异常类
  - `DataError`, `AlgorithmError`, `EvaluationError` 等

- **Config** (`config.py`): 配置管理
  - `Settings`: 应用设置（Pydantic模型）
  - `ConfigManager`: 配置管理器（支持环境配置、配置合并）

#### 2. Domain Layer (`et_dflow/domain/`)

**职责**: 业务逻辑实现

- **Algorithms** (`algorithms/`): 重构算法实现
  - `Algorithm`: 算法基类（Strategy模式）
  - `WBPAlgorithm`: WBP算法实现
  - `strategy.py`: 算法策略模式实现

- **Evaluation** (`evaluation/`): 评估指标实现
  - `chain.py`: 评估链（Chain of Responsibility模式）
  - `metrics/`: 各种评估指标（PSNR, SSIM, FSC等）

#### 3. Infrastructure Layer (`et_dflow/infrastructure/`)

**职责**: 基础设施实现

- **Data** (`data/`): 数据加载和处理
  - `factory.py`: 数据加载器工厂（Factory模式）
  - `loaders/`: 各种格式的加载器（MRC, TIFF, HDF5, Hyperspy）
  - `converters/`: 格式转换器（自动转换到Hyperspy格式）
  - `preprocessors.py`: 数据预处理器

- **Workflows** (`workflows/`): dflow工作流
  - `baseline_workflow.py`: 基准测试工作流
  - `ops/`: dflow OP实现
    - `DataPreparationOP`: 数据准备OP
    - `AlgorithmExecutionOP`: 算法执行OP
    - `EvaluationOP`: 评估OP
    - `ComparisonOP`: 比较和报告生成OP

- **Utils** (`utils/`): 工具类
  - `docker_validator.py`: Docker镜像验证器
  - `config_wizard.py`: 配置向导
  - `cache.py`: 缓存管理

- **Monitoring** (`monitoring/`): 监控和日志
- **Visualization** (`visualization/`): 可视化工具

#### 4. Application Layer (`et_dflow/application/`)

**职责**: 应用入口和编排

- **CLI** (`cli.py`): 命令行接口
  - `benchmark`: 运行基准测试
  - `validate`: 验证配置文件
  - `init`: 初始化配置
  - `quick-start`: 快速开始

- **Workflows** (`workflows/`): 工作流编排（可选，用于非dflow场景）

## Execution Flow

### 完整执行流程

```
用户命令
  ↓
CLI解析 (et_dflow/application/cli.py)
  ↓
配置加载和验证
  ↓
Docker镜像验证 (et_dflow/infrastructure/utils/docker_validator.py)
  ├─ 检查Docker可用性
  ├─ 检查镜像是否存在
  ├─ 拉取镜像（如需要）
  └─ 测试镜像可运行性
  ↓
工作流构建 (et_dflow/infrastructure/workflows/baseline_workflow.py)
  ↓
提交到dflow服务器
  ↓
┌─────────────────────────────────────────────────┐
│  dflow工作流执行（Kubernetes集群）              │
├─────────────────────────────────────────────────┤
│                                                  │
│  Step 1: Data Preparation                       │
│  ┌──────────────────────────────────────────┐  │
│  │ DataPreparationOP                         │  │
│  │  ├─ 格式检测 (mrc/tif/hspy)              │  │
│  │  ├─ 格式转换 (→ hspy)                    │  │
│  │  ├─ 数据预处理                           │  │
│  │  └─ 保存为hspy格式                       │  │
│  └──────────────────────────────────────────┘  │
│           ↓                                      │
│  Step 2: Algorithm Execution (并行)             │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │ Algorithm-1 OP   │  │ Algorithm-2 OP   │   │
│  │ (Docker容器)     │  │ (Docker容器)     │   │
│  │                  │  │                  │   │
│  │ 1. 加载输入数据  │  │ 1. 加载输入数据  │   │
│  │ 2. 执行算法      │  │ 2. 执行算法      │   │
│  │ 3. 保存结果      │  │ 3. 保存结果      │   │
│  │    - .hspy       │  │    - .hspy       │   │
│  │    - .npy       │  │    - .npy         │   │
│  └──────────────────┘  └──────────────────┘   │
│           ↓                    ↓               │
│  Step 3: Evaluation (并行)                     │
│  ┌──────────────────┐  ┌──────────────────┐   │
│  │ Evaluation-1 OP  │  │ Evaluation-2 OP  │   │
│  │  ├─ 加载重构结果 │  │  ├─ 加载重构结果 │   │
│  │  ├─ 计算指标     │  │  ├─ 计算指标     │   │
│  │  └─ 保存指标     │  │  └─ 保存指标     │   │
│  └──────────────────┘  └──────────────────┘   │
│           ↓                    ↓               │
│  Step 4: Comparison & Report                   │
│  ┌──────────────────────────────────────────┐  │
│  │ ComparisonOP                              │  │
│  │  ├─ 聚合所有评估结果                      │  │
│  │  ├─ 生成比较报告                          │  │
│  │  └─ 生成可视化                            │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
  ↓
结果返回
```

### 详细步骤说明

#### 1. CLI命令解析 (`et_dflow/application/cli.py`)

```python
@cli.command()
def benchmark(config_file, ...):
    # 1. 加载配置文件
    config = yaml.safe_load(config_file)
    
    # 2. 验证配置
    validator = ConfigValidator()
    validation_result = validator.validate(config)
    
    # 3. 远程模式下进行配置校验
    #    镜像实际由 Kubernetes worker 拉取，CLI 不再做本地 docker run 验证

    # 4. 构建并提交工作流
    workflow = BaselineBenchmarkWorkflow(config)
    workflow_id = workflow.submit()
```

#### 2. 数据准备OP (`DataPreparationOP`)

```python
def execute(self, op_in):
    # 1. 格式检测
    detected_format = factory._detect_format(dataset_path)
    
    # 2. 格式转换（如果非hspy）
    if detected_format != "hspy":
        converter = FormatConverter()
        signal = converter.convert_to_hyperspy(input_path, output_path)
    
    # 3. 数据预处理
    if preprocessing_steps:
        signal = preprocessor.preprocess(signal, preprocessing_steps)
    
    # 4. 保存为hspy格式
    signal.save(output_path)
```

#### 3. 算法执行OP (`AlgorithmExecutionOP`)

```python
def execute(self, op_in):
    # 1. 在当前远程step容器中执行算法
    #    (PythonOPTemplate(image=...) 指定算法镜像)
    subprocess.run([
        "python", "/app/run_algorithm.py",
        "--input", prepared_data,
        "--output", reconstruction_path,
        "--config", algorithm_config
    ])
    
    # 2. 加载结果
    reconstruction_signal = hs.load(reconstruction_path)
    
    # 3. 保存为多种格式
    #    - .hspy: Hyperspy/ETSpy-compatible volume
    #    - .npy: 纯numpy数组
    reconstruction_signal.save(hspy_path)
    np.save(npy_path, reconstruction_signal.data)
```

#### 4. 评估OP (`EvaluationOP`)

```python
def execute(self, op_in):
    # 1. 加载重构结果和ground truth
    reconstruction = hs.load(reconstruction_path)
    ground_truth = hs.load(ground_truth_path) if ground_truth_path else None
    
    # 2. 构建评估链（Chain of Responsibility模式）
    chain = build_evaluation_chain(metrics)
    
    # 3. 计算指标
    metrics_dict = chain.process(algorithm_result, ground_truth)
    
    # 4. 保存结果
    save_evaluation_results(metrics_dict)
```

## Key Features

### 1. 自动格式转换

系统支持多种输入格式（MRC, TIFF, HDF5等），并自动转换为内部统一格式（Hyperspy）：

- **格式检测**: 通过文件扩展名自动检测格式
- **自动转换**: 非hspy格式自动转换为hspy
- **缓存机制**: 转换后的文件保存到缓存目录
- **元数据保留**: 保留原始格式信息在metadata中

**实现位置**: `et_dflow/infrastructure/workflows/ops/data_preparation_op.py`

### 2. 多格式输出

算法执行后，结果保存为两种格式：

- **`.hspy`格式**: Hyperspy 原生 HDF5 格式，可被 ETSpy/Hyperspy 直接读取
- **`.npy`格式**: 纯NumPy数组，便于其他工具直接使用

**实现位置**: `et_dflow/infrastructure/workflows/ops/algorithm_execution_op.py`

### 3. Docker镜像预拉取和验证

在远程集群模式下，系统主要校验配置完整性；镜像真正由 Kubernetes worker 节点拉取和运行。若需要，可在 CI/CD 或集群侧单独做镜像可拉取检查。

**配置选项** (`configs/base.yaml`):
```yaml
docker:
  pre_pull: true  # 是否预拉取镜像
  validate_images: true  # 是否验证镜像
  validation_timeout: 30  # 验证超时时间（秒）
```

**CLI选项**:
```bash
# 正常使用（自动验证）
et-dflow benchmark config.yaml

# 跳过验证（不推荐，仅用于开发）
et-dflow benchmark config.yaml --skip-image-validation
```

**实现位置**: `et_dflow/infrastructure/utils/docker_validator.py`

## Design Patterns

### 1. Factory Pattern（工厂模式）

**用途**: 数据加载器创建

```python
# et_dflow/infrastructure/data/factory.py
factory = DataLoaderFactory()
loader = factory.create_loader("data.mrc")  # 自动选择MRCLoader
signal = loader.load("data.mrc")
```

### 2. Strategy Pattern（策略模式）

**用途**: 算法选择和执行

```python
# et_dflow/domain/algorithms/strategy.py
algorithm = AlgorithmStrategy.create("wbp")
result = algorithm.run(data, config)
```

### 3. Chain of Responsibility（责任链模式）

**用途**: 评估指标计算

```python
# et_dflow/domain/evaluation/chain.py
chain = build_evaluation_chain(['psnr', 'ssim', 'mse'])
metrics = chain.process(result, ground_truth)
```

### 4. Template Method（模板方法模式）

**用途**: 算法基类

```python
# et_dflow/domain/algorithms/base.py
class Algorithm:
    def run(self, data, config):
        # 模板方法：定义算法执行流程
        self.validate_input(data)
        result = self._execute(data, config)  # 子类实现
        return AlgorithmResult(...)
```

## Project Structure

```
ET-dflow/
├── et_dflow/              # Main package
│   ├── core/             # Core interfaces and models
│   │   ├── interfaces.py    # 核心接口定义
│   │   ├── models.py        # 数据模型
│   │   ├── exceptions.py    # 异常类
│   │   └── config.py        # 配置管理
│   ├── domain/           # Domain logic
│   │   ├── algorithms/      # 算法实现
│   │   └── evaluation/      # 评估指标
│   ├── infrastructure/   # Infrastructure
│   │   ├── data/            # 数据加载和转换
│   │   ├── workflows/      # dflow工作流
│   │   ├── utils/          # 工具类（包括docker_validator）
│   │   └── monitoring/     # 监控
│   └── application/     # Application layer
│       └── cli.py          # CLI入口
├── tests/                # Test suite
├── configs/              # Configuration files
├── docker/               # Docker configurations
│   └── algorithms/        # 算法Docker镜像配置
├── data/                 # Data files
│   ├── datasets/          # 数据集
│   └── metadata/          # 元数据模板
├── scripts/              # Utility scripts
├── templates/            # Templates
├── setup.py
├── pyproject.toml
├── requirements.txt
└── README.md
```

## Configuration

完整配置与 `configs/` 下的 base、algorithms、datasets 及环境变量（如 `DOCKER_REGISTRY`）的说明见 [Configuration Guide](docs/CONFIGURATION_GUIDE.md)。

### 配置文件结构

```yaml
# 数据集配置
datasets:
  test_dataset:
    path: "./data/datasets/test_dataset"
    format: "hyperspy"  # 支持: hyperspy, mrc, tiff, h5

# 算法配置
algorithms:
  wbp:
    enabled: true
    docker_image: "et-dflow/wbp:latest"  # 必需
    parameters:
      filter_type: "ramp"
    resources:
      cpu: 2
      memory: "4Gi"

# Docker配置
docker:
  pre_pull: true
  validate_images: true
  validation_timeout: 30

# 评估配置
evaluation:
  metrics:
    - "psnr"
    - "ssim"
    - "mse"
  ground_truth_path: "./data/ground_truth.hspy"

# 工作流配置
workflow:
  name: "baseline-benchmark"
  output_dir: "./results"
```

## Evaluation Tasks

The framework supports three main evaluation tasks:

1. **Baseline Benchmark**: Evaluate algorithms on datasets with ground truth under ideal conditions
2. **Missing Wedge Analysis**: Systematic investigation of missing wedge effects
3. **Experimental Data Evaluation**: Evaluate algorithms on real experimental data without ground truth

## Supported Algorithms

Configured in [configs/algorithms.yaml](configs/algorithms.yaml). Included:

- **WBP** (Weighted Back Projection), **SIRT**, **RESIRE**, **GENFIRE** — classic/iterative; repo provides Dockerfiles (wbp, sirt, resire; genfire may use external image).
- **DeepDeWedge**, **TIGRE**, **IsoNet**, **WUCon**, **ASTRA** — external pre-built images; see [External Docker Images](docs/EXTERNAL_DOCKER_IMAGES_INTEGRATION.md).
- Additional algorithms can be added via config and optional adapter scripts.

## Supported Data Formats

### 输入格式（自动转换）

- **Hyperspy** (.hspy) - 内部标准格式
- **MRC** (.mrc, .rec) - 电镜常用格式
- **TIFF** (.tif, .tiff) - 图像格式
- **HDF5** (.h5, .hdf5) - 科学数据格式

### 输出格式

- **`.hspy`** - Hyperspy 原生 HDF5 格式（可被 ETSpy/Hyperspy 直接读取）
- **`.npy`** - NumPy数组格式（便于其他工具使用）

## Docker镜像管理

### 构建镜像

```bash
# 构建本仓库提供的内部算法镜像（wbp、sirt、genfire、resire）
./scripts/build_docker_images.sh

# 或单独构建
docker build -f docker/algorithms/wbp/Dockerfile -t et-dflow/wbp:latest .
```

注意：
- `Dockerfile` 路径是 `docker/algorithms/wbp/Dockerfile`
- `build context` 必须是仓库根目录 `ET-dflow/`
- 如果在玻尔空间站或其他远端构建平台中只上传 `docker/algorithms/wbp/` 目录，会因为缺少根目录下的 `requirements.txt`、`setup.py`、`pyproject.toml` 和 `et_dflow/` 而构建失败

### 玻尔空间站构建 WBP 镜像

如果你的平台不支持把本地仓库文件 `COPY` 到镜像中，请使用：

```text
docker/algorithms/wbp/Dockerfile.bohr
```

这个 Dockerfile 的特点：

- 不依赖本地 `build context` 中的源码文件
- 在构建阶段通过 `git clone` 拉取 `ET-dflow` 仓库
- 自动安装 `requirements.txt`
- 安装 `et_dflow` 包并保留 `/app/run_algorithm.py` 入口

构建时需要提供以下 build args：

- `ET_DFLOW_REPO_URL`: 代码仓库地址
- `ET_DFLOW_REPO_REF`: 分支、tag 或 commit，默认是 `main`

逻辑上等价于：

```bash
docker build -f docker/algorithms/wbp/Dockerfile.bohr \
  --build-arg ET_DFLOW_REPO_URL=https://your.git.server/ET-dflow.git \
  --build-arg ET_DFLOW_REPO_REF=main \
  -t et-dflow/wbp:bohr .
```

在玻尔平台的界面中，关键点是：

- 选择 `docker/algorithms/wbp/Dockerfile.bohr`
- 填写可访问的 Git 仓库地址
- 如需构建可复现版本，固定 `ET_DFLOW_REPO_REF` 到 tag 或 commit

构建完成后，建议至少验证：

```bash
python /app/run_algorithm.py --help
python --version
```

如果后续你的主节点按需拉起这个镜像，仍然可以继续使用统一算法接口：

- `--input`
- `--output`
- `--config`

如果你已经完成 `wbp` 镜像构建，并且希望从主节点提交任务、由远端 worker 拉起该镜像执行，再把结果导回主节点，可直接参考：

- `configs/wbp_remote_benchmark.yaml`
- `docs/WBP_MASTER_NODE_RUN.md`

DeepDeWedge、TIGRE、IsoNet、WUCon、ASTRA 等使用外部镜像，无需本仓库构建；见 configs/algorithms.yaml 与 [External Docker Images](docs/EXTERNAL_DOCKER_IMAGES_INTEGRATION.md)。

### 镜像验证

系统在提交工作流前会自动验证所有必需的Docker镜像：

1. 检查Docker是否可用
2. 检查镜像是否在本地
3. 如果不存在，尝试拉取（如果配置允许）
4. 运行测试验证镜像可运行性

验证失败时会提供详细的错误信息和解决建议。

## Extending the Framework

### 添加新算法

1. **实现算法类**:
```python
# et_dflow/domain/algorithms/my_algorithm.py
from et_dflow.domain.algorithms.base import Algorithm

class MyAlgorithm(Algorithm):
    def __init__(self):
        super().__init__("my_algorithm")
    
    def _execute(self, data, config):
        # 实现算法逻辑
        return reconstruction
```

2. **创建Docker镜像**:
```dockerfile
# docker/algorithms/my_algorithm/Dockerfile
FROM python:3.10-slim
COPY et_dflow/ ./et_dflow/
COPY docker/algorithms/my_algorithm/run_algorithm.py /app/run_algorithm.py
```

3. **更新配置**:
```yaml
algorithms:
  my_algorithm:
    docker_image: "et-dflow/my_algorithm:latest"
```

### 添加新评估指标

1. **实现指标处理器**:
```python
# et_dflow/domain/evaluation/metrics/my_metric.py
from et_dflow.domain.evaluation.chain import MetricHandler

class MyMetricHandler(MetricHandler):
    def handle(self, result, ground_truth):
        # 计算指标
        return {"my_metric": value}
```

2. **注册到评估链**:
```python
# et_dflow/domain/evaluation/chain.py
def build_evaluation_chain(metrics):
    handlers = {
        "my_metric": MyMetricHandler,
        # ...
    }
```

## Documentation

- [Configuration Guide](docs/CONFIGURATION_GUIDE.md) — YAML configs, configs/ layout, and environment variables
- [Quick Start (Test Dataset)](docs/QUICK_START_TEST_DATASET.md) — Run with `simulated/test_dataset_v1`
- [External Docker Images](docs/EXTERNAL_DOCKER_IMAGES_INTEGRATION.md) — Using pre-built algorithm images
- [Ground Truth in ET](docs/GROUND_TRUTH_EXPLANATION.md) — Simulated vs experimental data and metrics
- [Contributing](CONTRIBUTING.md)

## License

MIT License - see LICENSE file for details

## Citation

If you use this framework in your research, please cite:

```bibtex
@software{et_dflow_benchmark,
  title = {ET-dflow Benchmark Framework},
  author = {Your Name},
  year = {2024},
  url = {https://github.com/yourusername/ET-dflow}
}
```

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Contact

For questions or issues, please open an issue on GitHub.
