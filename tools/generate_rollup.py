"""Generate the 78 x 200 cm QianPulse roll-up banner."""

from pathlib import Path
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from qianpulse.engine import (
    bootstrap_baseline_divergence,
    fingerprint_divergence,
    fuse_crossings,
)
from qianpulse.simulate import simulate_batch

DESKTOP = Path.home() / "Desktop"
W, H = 4606, 11811  # 78 x 200 cm at 150 DPI

PAPER = (239, 237, 231)
INK = (24, 29, 28)
MUTED = (104, 111, 107)
RULE = (197, 194, 185)
NIGHT = (17, 24, 32)
NIGHT_2 = (25, 35, 45)
WHITE = (242, 243, 239)
RED = (190, 70, 62)
GREEN = (94, 118, 106)
GOLD = (169, 130, 80)

SANS = "/System/Library/Fonts/Hiragino Sans GB.ttc"
SERIF = "/System/Library/Fonts/Supplemental/Songti.ttc"
LATIN = "/System/Library/Fonts/Supplemental/Georgia.ttf"
LATIN_BOLD = "/System/Library/Fonts/Supplemental/Georgia Bold.ttf"


def font(path, size, index=0):
    return ImageFont.truetype(path, size=size, index=index)


F = {
    "brand": font(SERIF, 118),
    "brand_en": font(LATIN, 39),
    "meta": font(SANS, 35),
    "hero": font(SERIF, 270),
    "hero_small": font(SERIF, 150),
    "body": font(SANS, 48),
    "body_small": font(SANS, 37),
    "label": font(SANS, 31),
    "section": font(SERIF, 105),
    "number": font(LATIN_BOLD, 105),
    "metric": font(LATIN_BOLD, 114),
    "metric_unit": font(SANS, 35),
    "footer": font(SANS, 29),
}


def text(draw, xy, value, key, fill=INK, anchor=None, spacing=8):
    draw.multiline_text(xy, value, font=F[key], fill=fill, anchor=anchor, spacing=spacing)


def line(draw, xy, fill=RULE, width=2):
    draw.line(xy, fill=fill, width=width)


def curve_points(grid, values, box):
    x0, y0, x1, y1 = box
    grid = np.asarray(grid)
    values = np.asarray(values)
    xs = x0 + (grid - grid.min()) / max(np.ptp(grid), 1e-9) * (x1 - x0)
    ys = y1 - values / max(values.max(), 1e-9) * (y1 - y0)
    return list(zip(xs.astype(int), ys.astype(int)))


def draw_polyline(draw, points, fill, width):
    if len(points) > 1:
        draw.line(points, fill=fill, width=width, joint="curve")


def main():
    baseline = simulate_batch(100, bridge_freq=7.8, seed=42)
    current = simulate_batch(100, bridge_freq=7.2, seed=142)
    base_fp = fuse_crossings(baseline)
    current_fp = fuse_crossings(current)
    bootstrap = bootstrap_baseline_divergence(baseline[:40], seed=50)
    threshold = bootstrap["threshold95"]
    divergence = fingerprint_divergence(base_fp["fingerprint"], current_fp["fingerprint"])

    image = Image.new("RGB", (W, H), PAPER)
    draw = ImageDraw.Draw(image)
    margin = 300

    # Header
    draw.rectangle((margin, 250, margin + 112, 362), fill=RED)
    text(draw, (margin + 56, 306), "黔", "body", fill=WHITE, anchor="mm")
    text(draw, (margin + 155, 255), "黔脉", "brand")
    text(draw, (margin + 530, 307), "QIANPULSE", "brand_en", fill=MUTED)
    text(draw, (W - margin, 294), "贵州山地桥梁移动感知", "meta", fill=MUTED, anchor="ra")
    line(draw, (margin, 435, W - margin, 435), width=3)

    # Main proposition
    text(draw, (margin, 690), "一辆车，是噪声。", "hero", fill=INK)
    text(draw, (margin, 1045), "一百辆车，是桥。", "hero", fill=INK)
    text(
        draw,
        (margin + 10, 1455),
        "把营运车辆变成贵州桥梁的移动感知网络",
        "body",
        fill=MUTED,
    )

    # Dark signal field
    field = (margin, 1710, W - margin, 4050)
    draw.rectangle(field, fill=NIGHT)
    x0, y0, x1, y1 = field
    for idx in range(6):
        yy = y0 + 350 + idx * 280
        line(draw, (x0 + 210, yy, x1 - 210, yy), fill=NIGHT_2, width=3)

    text(draw, (x0 + 180, y0 + 155), "桥梁动态指纹", "label", fill=(151, 165, 166))
    text(draw, (x1 - 180, y0 + 155), "100 次穿越融合", "label", fill=(151, 165, 166), anchor="ra")

    chart_box = (x0 + 190, y0 + 430, x1 - 190, y1 - 440)
    base_points = curve_points(base_fp["grid"], base_fp["fingerprint"], chart_box)
    current_points = curve_points(current_fp["grid"], current_fp["fingerprint"], chart_box)
    draw_polyline(draw, base_points, (151, 169, 159), 13)
    draw_polyline(draw, current_points, (222, 104, 95), 13)

    # Chart axes and labels
    line(draw, (chart_box[0], chart_box[3] + 25, chart_box[2], chart_box[3] + 25), fill=(77, 91, 101), width=3)
    for freq in [3, 6, 9, 12, 15]:
        xx = int(chart_box[0] + (freq - 3) / 12 * (chart_box[2] - chart_box[0]))
        text(draw, (xx, chart_box[3] + 85), str(freq), "label", fill=(136, 148, 151), anchor="ma")
    text(draw, (chart_box[2], chart_box[3] + 145), "频率 / Hz", "label", fill=(136, 148, 151), anchor="ra")

    legend_y = y1 - 225
    line(draw, (x0 + 190, legend_y, x0 + 300, legend_y), fill=(151, 169, 159), width=10)
    text(draw, (x0 + 330, legend_y), f"历史基线  {base_fp['dominant_frequency']:.2f} Hz", "label", fill=(190, 200, 196), anchor="lm")
    line(draw, (x0 + 1030, legend_y, x0 + 1140, legend_y), fill=(222, 104, 95), width=10)
    text(draw, (x0 + 1170, legend_y), f"当前状态  {current_fp['dominant_frequency']:.2f} Hz", "label", fill=(222, 181, 176), anchor="lm")

    # Three key metrics under main plot
    metric_y0, metric_y1 = 4200, 4850
    metric_w = (W - 2 * margin) // 3
    metrics = [
        ("融合样本", "100", "次穿越"),
        ("频率变化", f"{current_fp['dominant_frequency'] - base_fp['dominant_frequency']:+.2f}", "Hz"),
        ("指纹差异 / 阈值", f"{divergence:.3f}", f"/ {threshold:.3f}"),
    ]
    for idx, (label, value, unit) in enumerate(metrics):
        mx0 = margin + idx * metric_w
        if idx:
            line(draw, (mx0, metric_y0, mx0, metric_y1), width=2)
        text(draw, (mx0 + 45, metric_y0 + 95), label, "label", fill=MUTED)
        text(draw, (mx0 + 45, metric_y0 + 235), value, "metric", fill=RED if idx == 1 else INK)
        text(draw, (mx0 + 55, metric_y0 + 390), unit, "metric_unit", fill=MUTED)
    line(draw, (margin, metric_y0, W - margin, metric_y0), width=2)
    line(draw, (margin, metric_y1, W - margin, metric_y1), width=2)

    # How it works
    text(draw, (margin, 5180), "01", "number", fill=RED)
    text(draw, (margin + 215, 5198), "从车流中，留下桥的共同频率", "section")
    text(
        draw,
        (margin + 220, 5365),
        "单次穿越信号很脏；多车辆、多次穿越后，车辆差异相互抵消，\n桥梁共享的动态响应逐渐稳定显现。",
        "body_small",
        fill=MUTED,
        spacing=18,
    )

    # Convergence sequence
    seq_y0, seq_y1 = 5700, 6950
    counts = [1, 5, 10, 20, 100]
    cell_w = (W - 2 * margin) // len(counts)
    for idx, count in enumerate(counts):
        cx0 = margin + idx * cell_w
        cx1 = cx0 + cell_w
        if idx:
            line(draw, (cx0, seq_y0, cx0, seq_y1), width=2)
        fused = fuse_crossings(baseline[:count])
        text(draw, (cx0 + 35, seq_y0 + 70), str(count), "metric", fill=INK)
        text(draw, (cx0 + 45, seq_y0 + 215), "次", "label", fill=MUTED)
        box = (cx0 + 35, seq_y0 + 365, cx1 - 35, seq_y1 - 180)
        pts = curve_points(fused["grid"], fused["fingerprint"], box)
        line(draw, (box[0], box[3] + 10, box[2], box[3] + 10), width=2)
        draw_polyline(draw, pts, GREEN, 7)
        note = "证据不足" if count == 1 else ("共识形成" if count < 20 else "脉冲稳定")
        text(draw, (cx0 + 35, seq_y1 - 95), note, "label", fill=MUTED)
    line(draw, (margin, seq_y0, W - margin, seq_y0), width=2)
    line(draw, (margin, seq_y1, W - margin, seq_y1), width=2)

    # Screening logic
    text(draw, (margin, 7310), "02", "number", fill=RED)
    text(draw, (margin + 215, 7328), "异常不是猜出来的，只和桥自己的历史比", "section")
    text(
        draw,
        (margin + 220, 7495),
        "历史数据反复拆分，估计桥梁自身的自然波动范围。\n只有当前动态指纹越过 95% 阈值，才建议专业工程复核。",
        "body_small",
        fill=MUTED,
        spacing=18,
    )

    # Baseline distribution panel
    panel = (margin, 7890, W - margin, 9380)
    draw.rectangle(panel, fill=(229, 226, 217))
    px0, py0, px1, py1 = panel
    text(draw, (px0 + 110, py0 + 115), "基线自然波动与当前差异", "label", fill=MUTED)
    hist_x0, hist_y0, hist_x1, hist_y1 = px0 + 120, py0 + 350, px1 - 120, py1 - 210
    values = bootstrap["values"]
    hist, edges = np.histogram(values, bins=14, range=(0, max(divergence * 1.08, threshold * 2)))
    max_hist = max(hist.max(), 1)
    for idx, value in enumerate(hist):
        bx0 = hist_x0 + idx / len(hist) * (hist_x1 - hist_x0)
        bx1 = hist_x0 + (idx + 1) / len(hist) * (hist_x1 - hist_x0) - 5
        by0 = hist_y1 - value / max_hist * (hist_y1 - hist_y0)
        draw.rectangle((int(bx0), int(by0), int(bx1), hist_y1), fill=(124, 145, 134))
    line(draw, (hist_x0, hist_y1, hist_x1, hist_y1), width=3)
    threshold_x = int(hist_x0 + threshold / edges[-1] * (hist_x1 - hist_x0))
    current_x = int(hist_x0 + divergence / edges[-1] * (hist_x1 - hist_x0))
    line(draw, (threshold_x, hist_y0, threshold_x, hist_y1), fill=GOLD, width=8)
    line(draw, (current_x, hist_y0, current_x, hist_y1), fill=RED, width=10)
    text(draw, (threshold_x + 18, hist_y0), f"95% 阈值  {threshold:.3f}", "label", fill=(130, 95, 50))
    text(draw, (current_x - 18, hist_y0 + 70), f"当前差异  {divergence:.3f}", "label", fill=RED, anchor="ra")

    # Final recommendation
    text(draw, (margin, 9720), "检测到持续响应偏移", "hero_small", fill=INK)
    line(draw, (margin, 9995, margin + 55, 9995), fill=RED, width=12)
    text(draw, (margin + 95, 9955), "建议优先进行专业工程检查", "body", fill=RED)
    text(
        draw,
        (margin, 10110),
        "黔脉不做结构损伤诊断，不输出裂缝、失效或安全风险判断。\n它只回答一个问题：这座桥的动态响应，是否持续偏离了它自己的历史。",
        "body_small",
        fill=MUTED,
        spacing=18,
    )

    # Footer and 10 cm roll-up mechanism safety area
    footer_y = 10820
    line(draw, (margin, footer_y, W - margin, footer_y), width=3)
    text(draw, (margin, footer_y + 90), "黔脉 QianPulse", "body_small", fill=INK)
    text(draw, (W - margin, footer_y + 90), "现场演示 · 模拟数据 · 本机离线运行", "footer", fill=MUTED, anchor="ra")
    text(draw, (margin, footer_y + 225), "把营运车辆变成贵州桥梁的移动感知网络", "footer", fill=MUTED)
    # Keep the final ~10 cm visually quiet for the roll-up base.

    preview = image.copy()
    preview.thumbnail((1170, 3000), Image.Resampling.LANCZOS)

    jpg_path = DESKTOP / "黔脉_QianPulse_易拉宝_78x200cm_印刷版.jpg"
    tiff_path = DESKTOP / "黔脉_QianPulse_易拉宝_78x200cm_CMYK.tif"
    preview_path = DESKTOP / "黔脉_QianPulse_易拉宝_预览.png"

    image.save(jpg_path, "JPEG", quality=96, subsampling=0, dpi=(150, 150))
    image.convert("CMYK").save(tiff_path, "TIFF", compression="tiff_lzw", dpi=(150, 150))
    preview.save(preview_path, "PNG", optimize=True)

    print(jpg_path)
    print(tiff_path)
    print(preview_path)


if __name__ == "__main__":
    main()
