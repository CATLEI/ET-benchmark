# 使用 test_dataset_v1 快速启动指南

## test_dataset_v1 数据来源

根据项目文档，`test_dataset_v1` 的数据来源如下：

### 数据迁移历史

1. **原始位置**: `data/test_dataset/`
2. **迁移后位置**: `data/datasets/simulated/test_dataset_v1/`
3. **迁移说明**: 从旧的目录结构迁移到新的标准化数据集结构

### 数据集内容

```
data/datasets/simulated/test_dataset_v1/
├── README.md                    # 数据集说明
├── metadata.yaml                # 数据集元数据
├── raw/
│   ├── tilt_series.hspy        # 投影数据（从 test_data.hspy 迁移）
│   └── tilt_angles.txt         # 倾斜角度（如果存在）
└── ground_truth/
    └── volume.hspy             # Ground Truth 3D体积（从 ground_truth.hspy 迁移）
```

### 数据生成方式

原始数据可能通过以下方式生成：

1. **脚本生成**: `scripts/create_test_data.py` - 生成简单的合成测试数据
2. **手动创建**: 从其他来源导入的测试数据
3. **迁移**: 从旧版本项目迁移的数据

## 快速启动方法

### 方法1：使用预配置的配置文件（推荐）

#### 步骤1：检查Docker镜像

确保WBP算法的Docker镜像已构建：

```bash
# 检查镜像是否存在
docker images | grep et-dflow/wbp

# 如果不存在，构建镜像
docker build -f docker/algorithms/wbp/Dockerfile -t et-dflow/wbp:latest .
```

注意：如果你在玻尔空间站等远端平台构建镜像，`Dockerfile` 要指向 `docker/algorithms/wbp/Dockerfile`，但 `build context` 必须选择仓库根目录，而不是只选 `docker/algorithms/wbp/` 子目录。

#### 步骤2：使用配置文件启动

使用 `configs/local_dflow_test.yaml` 或 `configs/dflow_benchmark_example.yaml`：

```bash
# 使用本地测试配置
et-dflow benchmark configs/local_dflow_test.yaml

# 或使用示例配置
et-dflow benchmark configs/dflow_benchmark_example.yaml
```

**配置文件内容** (`configs/local_dflow_test.yaml`):
```yaml
datasets:
  test_dataset_v1:
    path: "./data/datasets/simulated/test_dataset_v1"
    tilt_series: "raw/tilt_series.hspy"
    format: "hyperspy"

algorithms:
  wbp:
    enabled: true
    docker_image: "et-dflow/wbp:latest"
    parameters:
      filter_type: "ramp"
      interpolation: "linear"
    resources:
      cpu: 2
      memory: "4Gi"
      gpu: 0

evaluation:
  metrics:
    - "psnr"
    - "ssim"
    - "mse"
  ground_truth_path: "./data/datasets/simulated/test_dataset_v1/ground_truth/volume.hspy"

workflow:
  name: "local-dflow-benchmark"
  type: "baseline_benchmark"
  output_dir: "./results/dflow_test"

dflow:
  host: "http://localhost:2746"
  namespace: "argo"
```

### 方法2：使用 quick-start 命令（简单模式）

如果您想快速测试，可以使用 `quick-start` 命令：

```bash
# 使用 quick-start 创建简单配置
et-dflow quick-start \
  ./data/datasets/simulated/test_dataset_v1/raw/tilt_series.hspy \
  --algorithm wbp \
  --output test_config.yaml

# 运行基准测试
et-dflow benchmark test_config.yaml
```

**注意**: `quick-start` 模式可能不支持ground truth评估，如果需要完整的评估功能，使用方法1。

### 方法3：自定义配置文件

创建您自己的配置文件：

```bash
# 1. 复制模板
cp configs/local_dflow_test.yaml my_config.yaml

# 2. 编辑配置文件（可选）
# 修改算法参数、资源限制等

# 3. 运行基准测试
et-dflow benchmark my_config.yaml
```

## 完整启动流程

### 前置条件检查

1. **Python环境**:
   ```bash
   python --version  # 需要 Python 3.10+
   pip list | grep et-dflow  # 确认已安装
   ```

2. **Docker环境**:
   ```bash
   docker --version  # 确认Docker已安装
   docker ps  # 确认Docker daemon运行中
   ```

3. **dflow环境**（如果使用dflow工作流）:
   ```bash
   # 检查dflow服务器是否可访问
   curl http://localhost:2746/healthz  # 或您的dflow服务器地址
   ```

4. **数据集文件**:
   ```bash
   # 确认数据集文件存在
   ls -la data/datasets/simulated/test_dataset_v1/raw/tilt_series.hspy
   ls -la data/datasets/simulated/test_dataset_v1/ground_truth/volume.hspy
   ```

### 详细启动步骤

#### 步骤1：构建Docker镜像（如果尚未构建）

```bash
# 构建WBP算法镜像
cd /Users/leilei/work/et-dflow-md/ET-dflow
docker build -f docker/algorithms/wbp/Dockerfile -t et-dflow/wbp:latest .

# 验证镜像构建成功
docker images | grep et-dflow/wbp
```

#### 步骤2：验证Docker镜像（自动执行）

运行benchmark命令时，系统会自动验证Docker镜像：

```bash
et-dflow benchmark configs/local_dflow_test.yaml
```

如果镜像验证失败，会显示错误信息。可以跳过验证（不推荐）：

```bash
et-dflow benchmark configs/local_dflow_test.yaml --skip-image-validation
```

#### 步骤3：运行基准测试

```bash
# 使用预配置的配置文件
et-dflow benchmark configs/local_dflow_test.yaml \
  --output-dir ./results/test_run \
  --verbose
```

**参数说明**:
- `--output-dir`: 指定结果输出目录
- `--verbose`: 显示详细日志
- `--dflow-host`: 指定dflow服务器地址（如果与配置文件不同）
- `--dflow-namespace`: 指定Kubernetes命名空间（如果与配置文件不同）

#### 步骤4：查看结果

```bash
# 查看结果目录
ls -la ./results/dflow_test/

# 结果目录结构
results/<time>/
├── data/
│   ├── prepared_data.hspy
│   └── prepared_data_ground_truth.hspy
├── wbp/
│   ├── reconstruction.hspy
│   ├── reconstruction.npy
│   └── evaluation.json
├── comparison_summary.json
└── comparison_report.html
```

## 配置文件详解

### 数据集配置

```yaml
datasets:
  test_dataset_v1:
    path: "./data/datasets/simulated/test_dataset_v1"  # 数据集根目录
    tilt_series: "raw/tilt_series.hspy"                # 投影数据相对路径
    format: "hyperspy"                                  # 数据格式
```

### 算法配置

```yaml
algorithms:
  wbp:
    enabled: true                                      # 是否启用
    docker_image: "et-dflow/wbp:latest"               # Docker镜像（必需）
    parameters:                                        # 算法参数
      filter_type: "ramp"                             # 滤波器类型
      interpolation: "linear"                          # 插值方法
    resources:                                         # 资源限制
      cpu: 2                                           # CPU核心数
      memory: "4Gi"                                     # 内存限制
      gpu: 0                                           # GPU数量
```

### 评估配置

```yaml
evaluation:
  metrics:                                             # 评估指标列表
    - "psnr"                                           # 峰值信噪比（需要GT）
    - "ssim"                                           # 结构相似性（需要GT）
    - "mse"                                            # 均方误差（需要GT）
  ground_truth_path: "./data/datasets/simulated/test_dataset_v1/ground_truth/volume.hspy"
```

### 工作流配置

```yaml
workflow:
  name: "local-dflow-benchmark"                       # 工作流名称
  type: "baseline_benchmark"                          # 工作流类型
  output_dir: "./results/dflow_test"                  # 输出目录
```

### dflow配置

```yaml
dflow:
  host: "http://localhost:2746"                       # dflow服务器地址
  namespace: "argo"                                    # Kubernetes命名空间
```

## 常见问题

### 1. Docker镜像不存在

**错误**: `Docker image et-dflow/wbp:latest not found`

**解决**:
```bash
# 构建镜像
docker build -f docker/algorithms/wbp/Dockerfile -t et-dflow/wbp:latest .
```

### 2. dflow服务器连接失败

**错误**: `Failed to connect to dflow server`

**解决**:
- 检查dflow服务器是否运行: `curl http://localhost:2746/healthz`
- 检查配置文件中的 `dflow.host` 设置
- 或使用环境变量: `export DFLOW_HOST=http://your-server:2746`

### 3. 数据集文件不存在

**错误**: `Dataset file not found`

**解决**:
```bash
# 检查文件是否存在
ls -la data/datasets/simulated/test_dataset_v1/raw/tilt_series.hspy

# 如果不存在，可能需要重新生成或迁移数据
```

### 4. Ground Truth文件不存在

**警告**: `Ground truth file not found, skipping GT-based metrics`

**解决**:
- 如果不需要GT评估，可以移除配置文件中的 `ground_truth_path`
- 或使用不需要GT的指标: `["consistency"]`

### 5. 内存不足

**错误**: `Out of memory`

**解决**:
- 在配置文件中减少资源使用:
  ```yaml
  resources:
    memory: "2Gi"  # 减少内存限制
  ```
- 或使用更小的数据集

## 验证运行

运行一个简单的验证命令：

```bash
# 验证配置文件
et-dflow validate configs/local_dflow_test.yaml

# 如果验证通过，运行基准测试
et-dflow benchmark configs/local_dflow_test.yaml --verbose
```

## 预期输出

成功运行后，您应该看到：

1. **Docker镜像验证**:
   ```
   Validating Docker images...
   [OK] Image et-dflow/wbp:latest validated successfully
   [OK] All Docker images validated successfully
   ```

2. **工作流提交**:
   ```
   Submitting workflow to dflow...
   Workflow ID: xxx-xxx-xxx
   Workflow submitted successfully
   ```

3. **结果文件**:
   ```
   Results saved to: ./results/dflow_test/
   ```

## 下一步

- 查看结果: `./results/dflow_test/`
- 添加更多算法: 编辑配置文件，添加 `sirt`, `genfire` 等
- 使用自己的数据: 替换数据集路径
- 自定义评估指标: 修改 `evaluation.metrics`

## 相关文档

- [Ground Truth说明](GROUND_TRUTH_EXPLANATION.md)
- [README](../README.md)
- [配置文件示例](../configs/)

