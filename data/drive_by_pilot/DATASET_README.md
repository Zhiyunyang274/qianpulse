# QianPulse drive-by pilot 数据集

本目录包含两组数据，页面上会分别明确标注，不混淆：

## 1. 真实开车采集（a*.zip / b*.zip）— REAL FIELD DATA

同一座平桥的 10 次真实穿越记录（iPhone 15 · Sensor Logger · 100 Hz）：

- `a1–a6.zip`：正方向（去程），6 次
- `b1–b4.zip`：反方向（回程），4 次
- 采集日期：2026-08-29
- 每个记录 ~24–47 秒，含重力投影所需 Gravity.csv
- **无 Annotation 桥窗标注、无 GPS**（采集时未开启）——系统按「全程窗口」模式处理

数据处理方式：
- 竖直向加速度由 Gravity.csv 重力投影得到（桥梁竖弯振动只出现在竖直向）
- 每次穿越提取 top-5 候选峰（等权投票），10 次共 50 票
- 融合主频稳定收敛于 **≈11.9 Hz**（n≥4 后波动 <0.1 Hz，正反两向互相印证）

## 2. 模拟演示数据（sim_drive_*.zip）— SIMULATED

3 次合成穿越（demo bridge `GZ-DEMO-017`），带完整标注/GPS/manifest，
用于演示桥窗提取与 GPS 对齐逻辑。**必须**以 `SIMULATED DRIVE-BY DATA` 标注展示，
不得作为真实测量结果呈现（见各 ZIP 内 SIMULATION_MANIFEST.json）。

## 目录约定

解析器（`qianpulse/io_driveby.py`）按文件名排序读取全部 ZIP；真实数据
（无 SIMULATION_MANIFEST.json）自动标记为 real，模拟数据自动标记为 simulated。
