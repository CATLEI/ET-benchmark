# ET-dflow 配置文件使用指南

本指南详细说明ET-dflow项目中所有配置文件的用途、调用关系和使用方法。

## 配置文件概览

### 核心配置文件（必需）

这些文件是系统运行的基础，必须保留：

1. **`base.yaml`** - 基础配置
   - **用途**: 所有环境的默认配置
   - **调用**: 被`ConfigManager`自动加载作为基础配置
   - **内容**: Docker设置、dflow设置、资源默认值、日志配置等

2. **`algorithms.yaml`** - 算法配置
   - **用途**: 统一管理所有算法配置（包括内部构建和外部预构建镜像）
   - **调用**: 被`base.yaml`引用（`algorithms: {}`），但实际内容在此文件
   - **内容**: 所有可用算法的Docker镜像、参数、资源配置
   - **状态**: ✅ 已合并`external_algorithms.yaml`，统一管理

3. **`datasets.yaml`** - 数据集配置
   - **用途**: 定义所有可用数据集的元数据
   - **调用**: 被`base.yaml`引用（`datasets: {}`）
   - **内容**: 数据集路径、格式、ground truth信息等

### 环境配置文件（可选）

用于多环境部署，根据环境变量选择：

4. **`dev.yaml`** - 开发环境配置
   - **用途**: 开发环境的覆盖配置（覆盖`base.yaml`）
   - **调用**: `ConfigManager`根据`env="dev"`参数加载
   - **特点**: 启用DEBUG日志、保存中间结果、降低并行度

5. **`test.yaml`** - 测试环境配置
   - **用途**: 测试环境的覆盖配置
   - **调用**: `ConfigManager`根据`env="test"`参数加载
   - **特点**: 禁用缓存、顺序执行、测试服务器地址

6. **prod.yaml** - 生产环境配置
   - **用途**: 生产环境的覆盖配置
   - **调用**: `ConfigManager`根据`env="prod"`参数加载
   - **特点**: INFO日志、启用监控、高并行度

### 示例配置文件（用户直接使用）

这些是完整的配置文件示例，用户可以直接使用或作为模板：

7. **`dflow_benchmark_example.yaml`** - dflow工作流示例
   - **用途**: 使用dflow的完整示例配置
   - **使用**: `et-dflow benchmark configs/dflow_benchmark_example.yaml`
   - **特点**: 包含完整的datasets、algorithms、evaluation配置

8. **`local_dflow_test.yaml`** - 本地dflow测试配置
   - **用途**: 本地测试dflow工作流的简化配置
   - **使用**: `et-dflow benchmark configs/local_dflow_test.yaml`
   - **特点**: 简化配置，适合快速测试

9. **`benchmark_external.yaml`** - 外部算法基准测试配置
   - **用途**: 使用外部Docker镜像的完整示例配置
   - **使用**: `et-dflow benchmark configs/benchmark_external.yaml`
   - **特点**: 展示如何使用外部预构建镜像

## 配置文件调用关系

### ConfigManager加载流程

```
ConfigManager(env="dev")
  ↓
加载 base.yaml (基础配置)
  ├─ algorithms: {} (空占位符)
  ├─ datasets: {} (空占位符)
  └─ 其他默认设置
  ↓
加载 dev.yaml (环境覆盖)
  └─ 覆盖base.yaml中的对应设置
  ↓
加载 user.yaml (可选，用户本地覆盖)
  └─ 覆盖dev.yaml中的对应设置
  ↓
最终合并配置
```

### 用户直接使用的配置文件

用户通过CLI直接指定配置文件：

```bash
et-dflow benchmark configs/dflow_benchmark_example.yaml
```

这些配置文件是**独立的**，不依赖ConfigManager的加载流程，直接包含所有必需的配置。

## 配置文件结构

### 完整配置文件结构

一个完整的benchmark配置文件应包含：

```yaml
# Dataset Configuration
datasets:
  dataset_name:
    path: "./data/datasets/simulated/dataset_name"
    tilt_series: "raw/tilt_series.hspy"
    format: "hyperspy"

# Algorithms Configuration
algorithms:
  algorithm_name:
    enabled: true
    docker_image: "registry/image:tag"  # 必需
    parameters:
      # 算法特定参数
    resources:
      cpu: 2
      memory: "4Gi"
      gpu: 0

# Evaluation Configuration
evaluation:
  metrics:
    - "psnr"
    - "ssim"
    - "mse"
  ground_truth_path: "./data/ground_truth/volume.hspy"  # 可选

# Workflow Configuration
workflow:
  name: "benchmark-name"
  type: "baseline_benchmark"
  output_dir: "./results"

# dflow Configuration (可选)
dflow:
  host: "http://localhost:2746"
  namespace: "argo"
```

## dflow 与 S3/MinIO

当前项目使用 **remote cluster mode**：主节点只负责提交 workflow，真正的 `data_preparation`、`algorithm_execution`、`evaluation`、`comparison` 步骤都在 Kubernetes/Argo worker 节点上运行。

提交 dflow 工作流时，框架会上传 Python 包（含本仓库代码）和输入/输出 artifact 到 S3 兼容存储（如 MinIO），供 Argo 步骤使用。因此必须提供：

1. **Argo/dflow 访问地址**
2. **可用的 S3/MinIO 存储**

若 MinIO 不在本机或端口不同，可在配置或环境中指定：
- **环境变量**：`DFLOW_S3_ENDPOINT=http://your-host:9000`、`DFLOW_S3_BUCKET_NAME=my-bucket`、`DFLOW_S3_ACCESS_KEY`、`DFLOW_S3_SECRET_KEY`
- **配置文件**：在 benchmark 的 YAML 的 `dflow` 段中设置 `s3_endpoint`、`s3_bucket_name` 等（见下表）。

### dflow 配置项（YAML 与环境变量）

| 用途 | YAML（`dflow` 段） | 环境变量 |
|------|---------------------|----------|
| 运行模式 | `mode: "remote"` | `DFLOW_MODE=remote` |
| Argo 地址 | `host`, `namespace` | `DFLOW_HOST`, `DFLOW_NAMESPACE` |
| Kubernetes API | `k8s_api_server` | `K8S_API_SERVER` |
| S3 端点 | `s3_endpoint: "http://host:9000"` | `DFLOW_S3_ENDPOINT` |
| S3 bucket | `s3_bucket_name: "my-bucket"` | `DFLOW_S3_BUCKET_NAME` |
| S3 认证 | `s3_access_key`, `s3_secret_key`, `s3_secure` | `DFLOW_S3_ACCESS_KEY`, `DFLOW_S3_SECRET_KEY`, `DFLOW_S3_SECURE` |

配置优先级：**环境变量 > benchmark YAML 的 `dflow` > 默认值**。

### 远程运行时的目录与结果位置

在 **remote cluster mode** 下，每次运行结束后，主节点会把 workflow 产物下载并整理到一个**按日期-时间命名的顶层目录**：

- **本次运行根目录**：`workflow.output_dir/<YYYYMMDD-HHMMSS>`（例如 `./results/20250226-143000`）。
- **数据目录**：`./results/<YYYYMMDD-HHMMSS>/data/`
  - `prepared_data.hspy`
  - `prepared_data_ground_truth.hspy`（如配置了 ground truth）
- **算法目录**：`./results/<YYYYMMDD-HHMMSS>/<alg_name>/`
  - `reconstruction.hspy`
  - `reconstruction.npy`
  - `evaluation.json`
- **汇总输出**：
  - `comparison_summary.json`
  - `comparison_report.html`

远程模式下，本地不再保存 `dflow_runs/` 调试目录，因为 step 运行发生在远端 Kubernetes/Argo worker 节点。

## 算法配置详解

### algorithms.yaml结构

所有算法统一在`algorithms.yaml`中管理：

```yaml
algorithms:
  wbp:
    name: "Weighted Back-Projection"
    docker_image: "${DOCKER_REGISTRY}/et-dflow/wbp:latest"
    category: "classic"
    parameters:
      filter_type: "ramp"
      filter_cutoff: 1.0
    resources:
      cpu: 2
      memory: "4Gi"
      gpu: false
  
  genfire:
    name: "GENFIRE"
    docker_image: "registry.dp.tech/davinci/genfire-python:20260110195114"
    category: "iterative"
    parameters:
      iterations: 100
    resources:
      cpu: 4
      memory: "8Gi"
      gpu: false
```

### 在benchmark配置中使用算法

在benchmark配置文件中，可以：

1. **直接引用算法**（使用algorithms.yaml中的默认配置）:
   ```yaml
   algorithms:
     wbp:
       enabled: true
       # 使用algorithms.yaml中的默认配置
   ```

2. **覆盖算法参数**:
   ```yaml
   algorithms:
     wbp:
       enabled: true
       docker_image: "custom/wbp:latest"  # 覆盖默认镜像
       parameters:
         filter_type: "custom"  # 覆盖默认参数
   ```

3. **添加新算法**（临时）:
   ```yaml
   algorithms:
     custom_alg:
       enabled: true
       docker_image: "custom/algorithm:latest"
       parameters:
         # 自定义参数
   ```

## 数据集配置详解

### datasets.yaml结构

```yaml
test_dataset_v1:
  name: "Test Dataset"
  type: "simulated"
  has_ground_truth: true
  path: "./data/datasets/simulated/test_dataset_v1"
  tilt_series: "raw/tilt_series.hspy"
  ground_truth: "ground_truth/volume.hspy"
  format: "hyperspy"
```

### 在benchmark配置中使用数据集

```yaml
datasets:
  test_dataset_v1:
    path: "./data/datasets/simulated/test_dataset_v1"
    tilt_series: "raw/tilt_series.hspy"
    format: "hyperspy"
```

## 环境变量支持

配置文件支持环境变量替换：

```yaml
docker:
  registry: "${DOCKER_REGISTRY}"  # 从环境变量读取
  namespace: "et-dflow"

dflow:
  host: "${DFLOW_HOST}"
  namespace: "${DFLOW_NAMESPACE}"
```

设置环境变量：

```bash
export DOCKER_REGISTRY=registry.dp.tech
export DFLOW_HOST=http://localhost:2746
export DFLOW_NAMESPACE=argo
```

## 配置文件优先级

当使用ConfigManager时，配置优先级为：

1. **user.yaml** (最高优先级)
2. **env.yaml** (dev/test/prod)
3. **base.yaml** (基础配置)

当直接使用benchmark配置文件时，该文件中的配置就是最终配置。

## 常见使用场景

### 场景1: 快速测试

使用预配置的示例文件：

```bash
et-dflow benchmark configs/local_dflow_test.yaml
```

### 场景2: 使用外部镜像

使用外部算法配置：

```bash
et-dflow benchmark configs/benchmark_external.yaml
```

### 场景3: 自定义配置

创建自己的配置文件：

```yaml
# my_benchmark.yaml
datasets:
  my_dataset:
    path: "./data/my_dataset"
    tilt_series: "raw/tilt_series.hspy"
    format: "hyperspy"

algorithms:
  wbp:
    enabled: true
    docker_image: "et-dflow/wbp:latest"
    parameters:
      filter_type: "ramp"

evaluation:
  metrics: ["psnr", "ssim"]
  ground_truth_path: "./data/my_dataset/ground_truth.hspy"

workflow:
  name: "my-benchmark"
  type: "baseline_benchmark"
  output_dir: "./results/my_benchmark"
```

运行：

```bash
et-dflow benchmark my_benchmark.yaml
```

## 配置文件验证

在运行前验证配置：

```bash
et-dflow validate configs/dflow_benchmark_example.yaml
```

验证会检查：
- 必需字段是否存在
- 算法是否都有docker_image
- 数据集路径是否存在
- 配置格式是否正确

## 已删除的文件

以下文件已被删除（过时或重复）：

- ❌ `test_benchmark.yaml` - 格式过时（使用`dataset`而非`datasets`）
- ❌ `genfire_deepdewedge_example.yaml` - 已被`benchmark_external.yaml`替代
- ❌ `external_algorithms.yaml` - 已合并到`algorithms.yaml`

## 最佳实践

1. **使用示例文件作为起点**: 复制示例文件并修改
2. **版本控制**: 将自定义配置文件纳入版本控制
3. **环境变量**: 使用环境变量管理敏感信息（registry认证等）
4. **验证配置**: 运行前先验证配置
5. **统一管理**: 所有算法在`algorithms.yaml`中统一管理

## 相关文档

- [快速启动指南](QUICK_START_TEST_DATASET.md)
- [外部镜像集成指南](EXTERNAL_DOCKER_IMAGES_INTEGRATION.md)
- [Ground Truth说明](GROUND_TRUTH_EXPLANATION.md)
- [README](../README.md)

