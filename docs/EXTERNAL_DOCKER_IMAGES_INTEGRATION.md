# 外部Docker镜像集成指南

本指南说明如何将已构建的外部Docker镜像集成到ET-dflow项目中使用。

## 概述

ET-dflow支持使用外部预构建的Docker镜像，这些镜像可能来自：
- 公共或私有Docker registry
- 其他项目构建的算法镜像
- 第三方提供的容器化算法

## 支持的镜像

当前项目已配置支持以下外部镜像：

1. **GENFIRE**: `registry.dp.tech/davinci/genfire-python:20260110195114`
2. **DeepDeWedge**: `registry.dp.tech/davinci/deepdewedge:20260113145259`
3. **TIGRE**: `registry.dp.tech/davinci/tigre:20260113153441`
4. **IsoNet**: `registry.dp.tech/davinci/isonet:20260113153511`
5. **WUCon**: `registry.dp.tech/davinci/wucon:20260113160259`
6. **ASTRA Toolbox**: `registry.dp.tech/davinci/astra-toolbox:20260113161211`

## 快速开始

### 1. 配置算法

在配置文件中添加外部算法：

```yaml
algorithms:
  genfire:
    enabled: true
    docker_image: "registry.dp.tech/davinci/genfire-python:20260110195114"
    parameters:
      iterations: 100
    resources:
      cpu: 4
      memory: "8Gi"
      gpu: false
```

### 2. 运行基准测试

```bash
et-dflow benchmark configs/benchmark_external.yaml
```

## 接口兼容性

### 标准接口

ET-dflow期望算法镜像提供标准接口：

- **脚本路径**: `/app/run_algorithm.py`
- **参数格式**:
  ```bash
  python /app/run_algorithm.py \
    --input <input_path> \
    --output <output_path> \
    --config <json_config>
  ```

### 外部镜像接口

外部镜像可能使用不同的接口：

1. **Python模块**: 直接导入Python模块（如 `import genfire`）
2. **命令行工具**: 使用特定的CLI命令（如 `ddw`, `isonet.py`）
3. **自定义入口点**: 使用自定义的ENTRYPOINT或CMD

## 解决方案

### 方案1：直接使用（如果镜像兼容标准接口）

如果外部镜像已经实现了标准接口，直接配置即可：

```yaml
algorithms:
  genfire:
    docker_image: "registry.dp.tech/davinci/genfire-python:20260110195114"
    # 无需额外配置，使用默认接口
```

### 方案2：使用自定义命令模板

如果镜像使用不同的命令格式，可以使用 `command_template`：

```yaml
algorithms:
  deepdewedge:
    docker_image: "registry.dp.tech/davinci/deepdewedge:20260113145259"
    command_template: "ddw --input {input} --output {output} --config {config}"
    parameters:
      iterations: 50
```

**占位符**:
- `{input}`: 输入数据路径
- `{output}`: 输出重构结果路径
- `{config}`: JSON格式的配置字符串

### 方案3：使用自定义入口点

如果镜像有自定义入口点，可以使用 `entrypoint`：

```yaml
algorithms:
  isonet:
    docker_image: "registry.dp.tech/davinci/isonet:20260113153511"
    entrypoint: "isonet.py"
    # 仍然使用标准参数: --input, --output, --config
```

### 方案4：创建适配器脚本（推荐用于复杂情况）

对于需要复杂转换的算法，创建适配器脚本：

1. **创建适配器脚本** (`docker/algorithms/genfire/run_algorithm.py`):

```python
#!/usr/bin/env python
"""
Adapter script for GENFIRE algorithm.
Converts standard ET-dflow interface to GENFIRE-specific interface.
"""
import argparse
import json
import sys
from pathlib import Path

import hyperspy.api as hs
import genfire

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--config", required=True)
    args = parser.parse_args()
    
    # Load config
    config = json.loads(args.config)
    
    # Load input data
    tilt_series = hs.load(args.input)
    
    # Call GENFIRE API
    # ... (GENFIRE-specific code)
    
    # Save output
    reconstruction.save(args.output)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

2. **在Dockerfile中复制适配器脚本**:

```dockerfile
# 在外部镜像基础上添加适配器
FROM registry.dp.tech/davinci/genfire-python:20260110195114

# Copy adapter script
COPY docker/algorithms/genfire/run_algorithm.py /app/run_algorithm.py
RUN chmod +x /app/run_algorithm.py
```

3. **使用新镜像**:

```yaml
algorithms:
  genfire:
    docker_image: "your-registry/genfire-with-adapter:latest"
```

## Registry认证

### 公共Registry

对于公共registry（如Docker Hub），通常不需要认证：

```bash
# 直接拉取
docker pull registry.dp.tech/davinci/genfire-python:20260110195114
```

### 私有Registry

对于私有registry，需要先登录：

```bash
# 登录到registry
docker login registry.dp.tech
# 输入用户名和密码

# 验证登录
docker pull registry.dp.tech/davinci/genfire-python:20260110195114
```

### Kubernetes中的认证

如果使用Kubernetes/dflow，需要创建imagePullSecret：

```bash
# 创建secret
kubectl create secret docker-registry regcred \
  --docker-server=registry.dp.tech \
  --docker-username=<username> \
  --docker-password=<password> \
  --docker-email=<email>

# 在Pod中使用（dflow会自动处理）
```

## 验证镜像

### 手动验证

在集成前，建议手动验证镜像：

```bash
# 1. 拉取镜像
docker pull registry.dp.tech/davinci/genfire-python:20260110195114

# 2. 测试镜像可运行
docker run --rm registry.dp.tech/davinci/genfire-python:20260110195114 python --version

# 3. 检查算法模块/命令
docker run --rm registry.dp.tech/davinci/genfire-python:20260110195114 \
  python3 -c "import genfire; print('genfire import OK')"
```

### 自动验证

ET-dflow会在提交工作流前自动验证镜像：

```bash
et-dflow benchmark configs/benchmark_external.yaml
# 系统会自动：
# 1. 检查Docker是否可用
# 2. 检查镜像是否存在
# 3. 拉取镜像（如果不存在且配置允许）
# 4. 测试镜像可运行性
```

## 配置示例

### 完整配置示例

```yaml
# configs/benchmark_external.yaml
datasets:
  test_dataset_v1:
    path: "./data/datasets/simulated/test_dataset_v1"
    tilt_series: "raw/tilt_series.hspy"
    format: "hyperspy"

algorithms:
  # 方案1: 直接使用（标准接口）
  genfire:
    enabled: true
    docker_image: "registry.dp.tech/davinci/genfire-python:20260110195114"
    parameters:
      iterations: 100
    resources:
      cpu: 4
      memory: "8Gi"
      gpu: false
  
  # 方案2: 使用自定义命令模板
  deepdewedge:
    enabled: true
    docker_image: "registry.dp.tech/davinci/deepdewedge:20260113145259"
    command_template: "ddw --input {input} --output {output}"
    parameters:
      iterations: 50
    resources:
      cpu: 4
      memory: "16Gi"
      gpu: 1
  
  # 方案3: 使用自定义入口点
  isonet:
    enabled: true
    docker_image: "registry.dp.tech/davinci/isonet:20260113153511"
    entrypoint: "isonet.py"
    parameters:
      # IsoNet参数
    resources:
      cpu: 4
      memory: "16Gi"
      gpu: 1

evaluation:
  metrics: ["psnr", "ssim", "mse"]
  ground_truth_path: "./data/datasets/simulated/test_dataset_v1/ground_truth/volume.hspy"

workflow:
  name: "external-algorithms-benchmark"
  type: "baseline_benchmark"
  output_dir: "./results/external_test"
```

## 常见问题

### 1. 镜像拉取失败

**错误**: `Authentication failed` 或 `Access denied`

**解决**:
```bash
# 登录到registry
docker login registry.dp.tech
```

### 2. 命令执行失败

**错误**: `executable file not found` 或 `No such file or directory`

**原因**: 镜像可能没有 `/app/run_algorithm.py` 或使用不同的命令格式

**解决**:
- 使用 `command_template` 指定正确的命令
- 或创建适配器脚本

### 3. GPU不可用

**错误**: `CUDA not available` 或 `GPU not found`

**解决**:
- 确保Kubernetes集群有GPU节点
- 检查资源配置中的 `gpu: 1` 设置
- 验证镜像是否支持GPU（某些镜像可能只支持CPU）

### 4. 数据格式不兼容

**错误**: `Unsupported file format` 或 `Cannot load data`

**解决**:
- 确保输入数据格式正确（.hspy格式）
- 检查算法是否支持该数据格式
- 可能需要数据预处理或格式转换

### 5. 内存不足

**错误**: `Out of memory` 或 `Killed`

**解决**:
- 增加资源配置中的内存限制
- 使用更小的数据集
- 优化算法参数

## 最佳实践

1. **先验证后使用**: 在集成前手动验证镜像
2. **使用适配器**: 对于复杂接口，创建适配器脚本
3. **文档化配置**: 记录每个算法的特殊配置要求
4. **版本管理**: 使用具体的镜像标签而非 `latest`
5. **资源规划**: 根据算法需求合理配置CPU/GPU/内存

## 相关文件

- 外部算法配置: `configs/external_algorithms.yaml`
- 示例配置: `configs/benchmark_external.yaml`
- 算法执行OP: `et_dflow/infrastructure/workflows/ops/algorithm_execution_op.py`
- Docker验证器: `et_dflow/infrastructure/utils/docker_validator.py`

## 下一步

- 查看[快速启动指南](QUICK_START_TEST_DATASET.md)了解如何使用test_dataset_v1
- 查看[Ground Truth说明](GROUND_TRUTH_EXPLANATION.md)了解评估指标
- 查看[README](../README.md)了解项目整体架构

