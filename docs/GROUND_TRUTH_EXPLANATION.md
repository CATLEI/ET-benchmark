# Ground Truth 在 ET-dflow 中的定义和使用

## 什么是 Ground Truth？

在电子断层扫描（ET）重构评估中，**Ground Truth** 是指**用于生成投影的原始3D体积（volume）**，而不是重构结果。

### 关键概念

```
模拟数据生成流程：
┌─────────────────┐
│  3D Volume      │  ← 这是 Ground Truth（已知的真实结构）
│  (Ground Truth) │
└────────┬────────┘
         │ 投影操作（Projection）
         │ 在不同角度下投影
         ↓
┌─────────────────┐
│  Tilt Series    │  ← 这是投影数据（从GT生成的）
│  (Projections)   │
└────────┬────────┘
         │ 重构算法（Reconstruction）
         │ WBP, SIRT, etc.
         ↓
┌─────────────────┐
│  Reconstruction │  ← 这是重构结果（需要与GT比较）
│  (Result)       │
└─────────────────┘
```

## 项目中的 Ground Truth

### 1. 模拟数据（Simulated Data）

对于模拟数据，ground truth 是**用于生成投影的原始3D体积**：

```yaml
# configs/datasets.yaml
test_dataset_v1:
  type: "simulated"
  has_ground_truth: true
  ground_truth: "ground_truth/volume.hspy"  # 原始3D体积
  tilt_series: "raw/tilt_series.hspy"        # 从GT生成的投影
```

**数据流程**：
1. **Ground Truth**: `ground_truth/volume.hspy` - 已知的3D结构
2. **投影生成**: 从GT在不同角度下生成投影 → `tilt_series.hspy`
3. **重构**: 使用算法从投影重构 → `reconstruction.hspy`
4. **评估**: 比较重构结果与GT → PSNR, SSIM, MSE等指标

### 2. 实验数据（Experimental Data）

对于实验数据，通常**没有真正的ground truth**，因为真实的3D结构是未知的：

```yaml
walnut_v1:
  type: "experimental"
  has_ground_truth: false  # 实验数据通常没有GT
  tilt_series: "raw/tilt_series.mrc"
```

**评估方法**（不需要GT）：
- **一致性检查**（Consistency）：重构结果与原始投影的一致性
- **FSC（Gold Standard）**：使用重构结果本身进行FSC计算
- **方向分辨率**：分析不同方向的分辨率

## 您的情况：180度全角度投影

如果您已经有了**180度全角度的投影**，需要确定：

### 情况1：模拟数据（有Ground Truth）

如果这些投影是从**已知的3D体积**生成的：

```
您需要提供：
├── raw/
│   └── tilt_series.hspy      # 您的180度投影数据
└── ground_truth/
    └── volume.hspy           # ⭐ 用于生成投影的原始3D体积（这就是GT）
```

**Ground Truth 就是**：用于生成这180度投影的原始3D体积。

### 情况2：实验数据（没有Ground Truth）

如果这些投影是**实验数据**（从真实样品采集的）：

```
您只需要：
└── raw/
    └── tilt_series.hspy      # 您的180度投影数据
```

**没有Ground Truth**，因为真实的3D结构是未知的。

### 情况3：使用重构结果作为参考

如果您想使用**180度投影重构的结果**作为参考：

⚠️ **注意**：这不是真正的ground truth，而是"参考重构"（Reference Reconstruction）

```
可能的做法：
├── raw/
│   └── tilt_series.hspy
└── reference/
    └── reconstruction.hspy    # 使用180度投影重构的结果作为参考
```

**评估方法**：
- 比较其他算法（使用部分角度）的重构结果与这个参考重构
- 这不是真正的ground truth评估，而是相对比较

## 如何准备 Ground Truth

### 对于模拟数据

如果您有180度全角度投影，并且知道这些投影是从哪个3D体积生成的：

1. **保存原始3D体积**：
   ```python
   import hyperspy.api as hs
   
   # 假设您有原始的3D体积数据
   volume = ...  # 您的3D数组 (depth, height, width)
   
   # 创建Hyperspy信号
   signal = hs.signals.Signal1D(volume)
   signal.metadata.set_item("pixel_size", 0.1)  # 像素大小（nm）
   
   # 保存为ground truth
   signal.save("ground_truth/volume.hspy")
   ```

2. **配置数据集**：
   ```yaml
   # configs/datasets.yaml
   my_dataset:
     type: "simulated"
     has_ground_truth: true
     ground_truth: "ground_truth/volume.hspy"
     tilt_series: "raw/tilt_series.hspy"
   ```

### 对于实验数据

如果您的投影是实验数据，通常没有ground truth：

1. **配置数据集**：
   ```yaml
   # configs/datasets.yaml
   my_dataset:
     type: "experimental"
     has_ground_truth: false
     tilt_series: "raw/tilt_series.hspy"
   ```

2. **使用无GT评估方法**：
   ```yaml
   # configs/benchmark.yaml
   evaluation:
     metrics:
       - "consistency"  # 一致性检查（不需要GT）
       # 不使用需要GT的指标：psnr, ssim, mse
   ```

## 评估指标与Ground Truth的关系

### 需要Ground Truth的指标

这些指标需要将重构结果与ground truth比较：

- **PSNR** (Peak Signal-to-Noise Ratio)
- **SSIM** (Structural Similarity Index)
- **MSE** (Mean Squared Error)
- **FSC with GT** (Fourier Shell Correlation with Ground Truth)

```python
# et_dflow/domain/evaluation/chain.py
class PSNRMetricHandler(MetricHandler):
    def handle(self, result, ground_truth):
        if ground_truth is None:
            return {}  # 无法计算，返回空
        # 计算PSNR...
```

### 不需要Ground Truth的指标

这些指标只需要重构结果和原始投影：

- **Consistency** (一致性检查)
- **FSC (Gold Standard)** (使用重构结果本身)
- **Directional Resolution** (方向分辨率)

## 总结

### 关键点

1. **Ground Truth ≠ 重构结果**
   - Ground Truth是用于生成投影的原始3D体积
   - 重构结果是算法从投影重构出的3D体积

2. **180度全角度投影的情况**
   - 如果投影是从已知3D体积生成的 → 那个3D体积就是GT
   - 如果投影是实验数据 → 通常没有GT
   - 可以使用180度投影的重构结果作为"参考"，但不是真正的GT

3. **评估方法选择**
   - 有GT：使用PSNR, SSIM, MSE等定量指标
   - 无GT：使用一致性、FSC (Gold Standard)等方法

### 建议

对于您的情况（有180度全角度投影）：

1. **确认数据来源**：
   - 如果是模拟数据，找到用于生成投影的原始3D体积作为GT
   - 如果是实验数据，使用无GT评估方法

2. **如果使用重构结果作为参考**：
   - 明确标注为"参考重构"而非"ground truth"
   - 使用相对比较方法，而非绝对定量评估

3. **配置评估**：
   ```yaml
   evaluation:
     metrics:
       - "psnr"   # 如果有GT
       - "ssim"   # 如果有GT
       - "consistency"  # 如果无GT
   ground_truth_path: "./data/ground_truth/volume.hspy"  # 如果有GT
   ```

## 相关文件

- 数据集配置：`configs/datasets.yaml`
- 评估链实现：`et_dflow/domain/evaluation/chain.py`
- 数据准备OP：`et_dflow/infrastructure/workflows/ops/data_preparation_op.py`
- 评估OP：`et_dflow/infrastructure/workflows/ops/evaluation_op.py`

