# QianPulse · 黔脉

把营运车辆变成贵州桥梁的移动感知网络。QianPulse 使用车辆经过桥梁时的 IMU 加速度，经过频域分析与多次穿越统计融合，建立桥梁动态响应的 Bridge Pulse baseline，并筛查持续的 response shift。

## Quick Start

```bash
cd qianpulse_starter
./run_demo.sh
```

或直接运行：

```bash
source .venv/bin/activate
streamlit run app.py
```

## Demo flow

- **One vehicle is noisy**：单次 crossing 的原始加速度与 PSD，明确显示证据不足。
- **The bridge emerges from the crowd**：1/5/10/20/50/100 次 crossing 的 KDE / consensus fingerprint 与 convergence 曲线。
- **Baseline vs Current**：默认 7.8 Hz baseline 对比 7.2 Hz current，使用 baseline 内部 bootstrap 的 95th percentile Jensen–Shannon divergence threshold。
- 点击侧边栏 **Run QianPulse Demo** 可播放一键 replay。

默认模式为 `SIMULATED DEMO DATA`，固定 seed 保证现场演示稳定、完全离线。

## Import iPhone Sensor Logger data

在侧边栏切换到 `REAL · Sensor Logger`，上传 Sensor Logger 导出的 CSV 或 ZIP。解析器会自动寻找 accelerometer CSV、识别 timestamp / seconds_elapsed 与 x/y/z 字段，估计 sampling rate，并输出统一 crossing 结构。没有可识别文件时会安全回退到模拟数据。

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Technical boundary

QianPulse detects persistent changes in a bridge's dynamic response relative to its own historical baseline. **It does not diagnose structural damage and does not replace professional bridge inspection.** 输出仅为 `Recommend targeted engineering inspection.`，不输出裂缝、失效或安全风险判断。
