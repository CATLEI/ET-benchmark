#!/usr/bin/env python3
"""Generate an illustrated PPT explaining MSE / PSNR / SSIM with vivid diagrams."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import patches
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Cm, Pt, Inches

PRIMARY = RGBColor(0x1F, 0x3A, 0x68)
ACCENT = RGBColor(0xC4, 0x5C, 0x26)
GOOD = RGBColor(0x2E, 0x7D, 0x4F)
WARN = RGBColor(0xC9, 0x8A, 0x20)
BAD = RGBColor(0xB0, 0x3A, 0x2E)
GREY = RGBColor(0x5A, 0x5A, 0x5A)
LIGHT = RGBColor(0xEE, 0xF1, 0xF6)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SOFT_BLUE = RGBColor(0x4A, 0x6F, 0xA5)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out" / "MSE_PSNR_SSIM讲解.pptx"
FIG_DIR = ROOT / "out" / "metrics_ppt_figs"


def _set_fill(shape, color: RGBColor) -> None:
    shape.fill.solid()
    shape.fill.fore_color.rgb = color


def _no_line(shape) -> None:
    shape.line.fill.background()


def add_rect(slide, left, top, width, height, color, *, corner=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if corner else MSO_SHAPE.RECTANGLE
    sh = slide.shapes.add_shape(shape_type, Cm(left), Cm(top), Cm(width), Cm(height))
    _set_fill(sh, color)
    _no_line(sh)
    if corner:
        try:
            sh.adjustments[0] = 0.12
        except Exception:
            pass
    return sh


def add_textbox(
    slide,
    text,
    *,
    left,
    top,
    width,
    height,
    size_pt=18,
    bold=False,
    color=PRIMARY,
    align=PP_ALIGN.LEFT,
):
    tb = slide.shapes.add_textbox(Cm(left), Cm(top), Cm(width), Cm(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(size_pt)
    run.font.bold = bold
    run.font.color.rgb = color
    return tb


def page_header(slide, title: str, subtitle: str | None = None):
    add_rect(slide, 0, 0, 33.87, 0.35, PRIMARY)
    add_textbox(slide, title, left=1.6, top=0.65, width=30, height=1.0, size_pt=26, bold=True)
    if subtitle:
        add_textbox(slide, subtitle, left=1.6, top=1.55, width=30, height=0.6, size_pt=13, color=GREY)


def add_picture(slide, path: Path, left, top, width):
    slide.shapes.add_picture(str(path), Cm(left), Cm(top), width=Cm(width))


# ---------------- figure generation ----------------

def _style_ax(ax):
    ax.set_xticks([])
    ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)


def make_figures():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    # --- MSE: GT / recon / error heat ---
    yy, xx = np.mgrid[0:48, 0:48]
    gt = np.exp(-((xx - 24) ** 2 + (yy - 24) ** 2) / (2 * 8 ** 2))
    recon = np.exp(-((xx - 26) ** 2 + (yy - 23) ** 2) / (2 * 11 ** 2)) * 0.85
    err = np.abs(gt - recon)

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6), dpi=160)
    for ax, img, title, cmap in zip(
        axes,
        [gt, recon, err],
        ["真值 GT\n（清晰亮斑）", "重建结果\n（偏糊、略偏移）", "误差热图 |差|\n（越红差越大）"],
        ["gray", "gray", "hot"],
    ):
        ax.imshow(img, cmap=cmap, origin="lower")
        ax.set_title(title, fontsize=12, pad=8)
        _style_ax(ax)
        # draw pixel grid feel
        ax.set_xlim(-0.5, 47.5)
        ax.set_ylim(-0.5, 47.5)
    # arrows
    fig.text(0.355, 0.48, "→", fontsize=28, color="#4A6FA5", ha="center")
    fig.text(0.655, 0.48, "→", fontsize=28, color="#4A6FA5", ha="center")
    fig.suptitle("MSE 的画面：逐格对拍 → 差的平方再平均", fontsize=14, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "mse_grids.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- MSE cartoon: pixel squares with numbers ---
    fig, ax = plt.subplots(figsize=(10, 3.8), dpi=160)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    ax.set_title("把体积想成一排小格子：每个格子算一次 (差)²", fontsize=13, fontweight="bold", pad=10)

    gt_vals = [0.9, 0.7, 0.4, 0.2]
    rc_vals = [0.8, 0.5, 0.45, 0.35]
    for i, (g, r) in enumerate(zip(gt_vals, rc_vals)):
        x = 0.4 + i * 2.9
        # GT cell
        ax.add_patch(patches.FancyBboxPatch((x, 2.5), 1.1, 1.1, boxstyle="round,pad=0.03", facecolor=plt.cm.gray(g), edgecolor="#1F3A68", lw=1.5))
        ax.text(x + 0.55, 3.05, f"{g:.1f}", ha="center", va="center", fontsize=11, color="white" if g < 0.55 else "black")
        ax.text(x + 0.55, 3.75, "GT", ha="center", fontsize=9, color="#5A5A5A")
        # recon cell
        ax.add_patch(patches.FancyBboxPatch((x + 1.25, 2.5), 1.1, 1.1, boxstyle="round,pad=0.03", facecolor=plt.cm.gray(r), edgecolor="#C45C26", lw=1.5))
        ax.text(x + 1.8, 3.05, f"{r:.1f}", ha="center", va="center", fontsize=11, color="white" if r < 0.55 else "black")
        ax.text(x + 1.8, 3.75, "重建", ha="center", fontsize=9, color="#5A5A5A")
        d2 = (g - r) ** 2
        ax.annotate("", xy=(x + 1.2, 2.35), xytext=(x + 1.2, 1.55), arrowprops=dict(arrowstyle="->", color="#B03A2E"))
        ax.text(x + 1.2, 1.15, f"(差)²={d2:.2f}", ha="center", fontsize=10, color="#B03A2E", fontweight="bold")

    mse = np.mean([(g - r) ** 2 for g, r in zip(gt_vals, rc_vals)])
    ax.text(6, 0.35, f"MSE = 平均这些 (差)²  ≈  {mse:.3f}   →  越小越好", ha="center", fontsize=12, color="#1F3A68", fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "mse_pixels.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- PSNR: peak vs noise + dB gauge ---
    fig = plt.figure(figsize=(11, 4.2), dpi=160)
    ax1 = fig.add_axes([0.06, 0.15, 0.42, 0.7])
    ax2 = fig.add_axes([0.55, 0.15, 0.4, 0.7])

    # bar metaphor
    ax1.bar([0], [1.0], width=0.55, color="#1F3A68", label="峰值 max(GT)")
    ax1.bar([1.2], [0.22], width=0.55, color="#B03A2E", label="误差 √MSE")
    ax1.set_ylim(0, 1.25)
    ax1.set_xticks([0, 1.2])
    ax1.set_xticklabels(["峰值信号", "误差噪声"], fontsize=11)
    ax1.set_yticks([])
    ax1.set_title("形象：高峰 vs 噪声矮柱", fontsize=12, fontweight="bold")
    for sp in ("top", "right", "left"):
        ax1.spines[sp].set_visible(False)
    ax1.legend(frameon=False, loc="upper right")
    ax1.annotate("比值越大 → 越干净", xy=(0.6, 0.7), fontsize=10, color="#C45C26")

    # dB scale
    levels = [20, 25, 30, 35, 40, 45]
    colors = ["#B03A2E", "#C98A20", "#C98A20", "#4A6FA5", "#2E7D4F", "#2E7D4F"]
    labels = ["雾里看花", "偏差明显", "常用门槛", "相当接近", "细节也好", "几乎贴合"]
    ax2.barh(levels, [1] * len(levels), height=3.5, color=colors, edgecolor="white")
    for y, lab in zip(levels, labels):
        ax2.text(0.5, y, f"{y} dB  ·  {lab}", ha="center", va="center", color="white", fontsize=10, fontweight="bold")
    ax2.set_xlim(0, 1)
    ax2.set_ylim(16, 48)
    ax2.set_xticks([])
    ax2.set_ylabel("PSNR (dB) ↑ 越大越好", fontsize=11)
    ax2.set_title("分贝尺经验刻度", fontsize=12, fontweight="bold")
    for sp in ("top", "right", "bottom"):
        ax2.spines[sp].set_visible(False)

    fig.suptitle("PSNR = 20 * log10(峰值 / sqrt(MSE))  ——  把误差换成“分贝信噪”", fontsize=13, fontweight="bold")
    fig.savefig(FIG_DIR / "psnr_gauge.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- SSIM three faces / blobs ---
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), dpi=160)
    yy, xx = np.mgrid[-1:1:80j, -1:1:80j]
    base = np.exp(-(xx ** 2 + yy ** 2) / 0.35)

    # luminance: same structure different mean
    bright = 0.35 + 0.55 * base
    dark = 0.10 + 0.35 * base
    axes[0].imshow(np.hstack([dark, bright]), cmap="gray", vmin=0, vmax=1)
    axes[0].set_title("① 亮度\n整体明暗是否同档", fontsize=11)
    axes[0].text(40, 72, "偏暗", ha="center", color="white", fontsize=9)
    axes[0].text(120, 72, "偏亮", ha="center", color="white", fontsize=9)

    # contrast
    low_c = 0.45 + 0.15 * base
    high_c = 0.15 + 0.75 * base
    axes[1].imshow(np.hstack([low_c, high_c]), cmap="gray", vmin=0, vmax=1)
    axes[1].set_title("② 对比度\n黑白反差是否同档", fontsize=11)
    axes[1].text(40, 72, "低对比", ha="center", color="white", fontsize=9)
    axes[1].text(120, 72, "高对比", ha="center", color="white", fontsize=9)

    # structure: same vs scrambled phase
    struct_ok = base
    struct_bad = np.exp(-((xx - 0.35) ** 2 + (yy + 0.25) ** 2) / 0.12) + 0.4 * np.exp(-((xx + 0.4) ** 2 + (yy - 0.35) ** 2) / 0.1)
    struct_bad = struct_bad / struct_bad.max()
    axes[2].imshow(np.hstack([struct_ok, struct_bad]), cmap="gray", vmin=0, vmax=1)
    axes[2].set_title("③ 结构\n起伏走势是否同向", fontsize=11)
    axes[2].text(40, 72, "同结构", ha="center", color="white", fontsize=9)
    axes[2].text(120, 72, "乱结构", ha="center", color="white", fontsize=9)

    for ax in axes:
        _style_ax(ax)
        ax.axvline(79.5, color="#C45C26", lw=2, ls="--")

    fig.suptitle("SSIM = 亮度 × 对比度 × 结构   ——  三项都像，分数才接近 1", fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ssim_components.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- SSIM score continuum with example pairs ---
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.2), dpi=160)
    scores = [0.35, 0.62, 0.85, 0.97]
    titles = ["完全不像", "有点像", "挺像", "几乎一样"]
    colors = ["#B03A2E", "#C98A20", "#4A6FA5", "#2E7D4F"]
    for ax, sc, title, col in zip(axes, scores, titles, colors):
        noise = 0.15 * (1 - sc) * np.random.RandomState(int(sc * 100)).randn(*base.shape)
        img = np.clip(base * (0.5 + 0.5 * sc) + noise, 0, 1)
        ax.imshow(img, cmap="gray")
        ax.set_title(f"SSIM ≈ {sc:.2f}\n{title}", fontsize=11, color=col, fontweight="bold")
        _style_ax(ax)
    fig.suptitle("SSIM 刻度：越接近 1，结构越“同款”", fontsize=13, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "ssim_scale.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- trio comparison cartoon ---
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=160)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 4)
    ax.axis("off")
    cards = [
        (0.4, "MSE", "逐格对拍差", "越小越好 ↓", "#B03A2E", "像用尺子量每格偏差"),
        (4.2, "PSNR", "分贝信噪尺", "越大越好 ↑", "#4A6FA5", "把误差换成相对峰值的响度"),
        (8.0, "SSIM", "同款鉴定", "越近1越好 ↑", "#2E7D4F", "亮度·对比·结构一起看"),
    ]
    for x, name, tag, tip, col, desc in cards:
        ax.add_patch(patches.FancyBboxPatch((x, 0.4), 3.5, 3.2, boxstyle="round,pad=0.08", facecolor="#EEF1F6", edgecolor=col, lw=2.5))
        ax.text(x + 1.75, 3.1, name, ha="center", fontsize=18, fontweight="bold", color=col)
        ax.text(x + 1.75, 2.45, tag, ha="center", fontsize=12, color="#1F3A68")
        ax.text(x + 1.75, 1.75, tip, ha="center", fontsize=13, fontweight="bold", color=col)
        ax.text(x + 1.75, 0.95, desc, ha="center", fontsize=9, color="#5A5A5A")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "trio.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    # --- combo reading scenes ---
    fig, axes = plt.subplots(2, 2, figsize=(10, 6.2), dpi=150)
    yy2, xx2 = np.mgrid[0:48, 0:48]
    gt2 = np.exp(-((xx2 - 24) ** 2 + (yy2 - 24) ** 2) / (2 * 8 ** 2))
    cases = [
        ("三项都好", gt2, gt2 * 0.98 + 0.01, "#2E7D4F"),
        ("PSNR 尚可 · SSIM 偏低（糊了）", gt2, np.exp(-((xx2 - 24) ** 2 + (yy2 - 24) ** 2) / (2 * 16 ** 2)), "#C98A20"),
        ("SSIM 尚可 · MSE 偏高（偏亮）", gt2, np.clip(gt2 * 0.7 + 0.35, 0, 1), "#C45C26"),
        ("三项都差 · 先查对齐", gt2, np.roll(gt2, 12, axis=1), "#B03A2E"),
    ]
    for ax, (title, a, b, col) in zip(axes.ravel(), cases):
        panel = np.hstack([a, b])
        ax.imshow(panel, cmap="gray", vmin=0, vmax=1)
        ax.axvline(47.5, color=col, lw=2)
        ax.set_title(title, fontsize=11, color=col, fontweight="bold")
        ax.text(24, -3, "GT", ha="center", fontsize=9, color="#5A5A5A")
        ax.text(72, -3, "重建", ha="center", fontsize=9, color="#5A5A5A")
        _style_ax(ax)
    fig.suptitle("组合解读：同一场景，不同“病症”", fontsize=14, fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "combo.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)

    return {
        "mse_grids": FIG_DIR / "mse_grids.png",
        "mse_pixels": FIG_DIR / "mse_pixels.png",
        "psnr_gauge": FIG_DIR / "psnr_gauge.png",
        "ssim_components": FIG_DIR / "ssim_components.png",
        "ssim_scale": FIG_DIR / "ssim_scale.png",
        "trio": FIG_DIR / "trio.png",
        "combo": FIG_DIR / "combo.png",
    }


def build_pptx(figs: dict) -> Presentation:
    prs = Presentation()
    prs.slide_width = Cm(33.87)
    prs.slide_height = Cm(19.05)
    blank = prs.slide_layouts[6]

    # 1 cover
    s = prs.slides.add_slide(blank)
    add_rect(s, 0, 0, 33.87, 19.05, PRIMARY)
    add_rect(s, 0, 14.8, 33.87, 4.25, RGBColor(0x16, 0x2C, 0x4F))
    add_textbox(s, "图像 / 体积质量三剑客", left=2, top=4.2, width=30, height=1.0, size_pt=20, color=RGBColor(0xA8, 0xC0, 0xE0), align=PP_ALIGN.CENTER)
    add_textbox(s, "MSE · PSNR · SSIM", left=2, top=5.8, width=30, height=1.8, size_pt=48, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    add_textbox(s, "用形象示意图读懂三大评估指标\n面向电子断层重建与体积对比", left=4, top=8.5, width=26, height=2.0, size_pt=16, color=RGBColor(0xC5, 0xD4, 0xE8), align=PP_ALIGN.CENTER)
    add_textbox(s, "ET-benchmark 教学课件", left=2, top=16.3, width=30, height=0.8, size_pt=14, color=RGBColor(0x9A, 0xB0, 0xC8), align=PP_ALIGN.CENTER)

    # 2 trio overview
    s = prs.slides.add_slide(blank)
    page_header(s, "今天要记住的三幅画面", "先建立直觉，再碰公式")
    add_picture(s, figs["trio"], 1.8, 3.0, 30.2)
    add_textbox(s, "三者都需要 GT；本流水线会先把重建对齐到真值，再算指标。", left=1.8, top=16.8, width=30, height=0.8, size_pt=13, color=GREY, align=PP_ALIGN.CENTER)

    # 3 MSE visual
    s = prs.slides.add_slide(blank)
    page_header(s, "MSE：像两张照片逐格对拍", "Mean Squared Error · 均方误差 · 越小越好")
    add_picture(s, figs["mse_grids"], 1.5, 2.5, 30.8)
    add_textbox(
        s,
        "中间亮斑变糊 / 偏移 → 热图发红；平方会放大离谱坏点。完全一致时 MSE = 0。",
        left=1.8, top=16.5, width=30, height=1.0, size_pt=14, color=GREY, align=PP_ALIGN.CENTER,
    )

    # 4 MSE pixel story
    s = prs.slides.add_slide(blank)
    page_header(s, "MSE 在算什么？（格子版）", "对齐 → 求差 → 平方 → 平均")
    add_picture(s, figs["mse_pixels"], 1.5, 2.8, 30.8)
    add_textbox(
        s,
        "公式：MSE = (1/N) Σ (xᵢ − yᵢ)²    ｜  局限：只看数值差，不直接反映结构像不像。",
        left=1.8, top=16.3, width=30, height=1.2, size_pt=14, color=PRIMARY, align=PP_ALIGN.CENTER,
    )

    # 5 PSNR
    s = prs.slides.add_slide(blank)
    page_header(s, "PSNR：信号高峰 vs 误差噪声", "Peak Signal-to-Noise Ratio · 越大越好（dB）")
    add_picture(s, figs["psnr_gauge"], 1.5, 2.5, 30.8)
    add_textbox(
        s,
        "本仓库峰值取 GT 最大值（不是固定 255）；MSE=0 时理论为无穷大。MSE↓ ⇒ PSNR↑。",
        left=1.8, top=16.5, width=30, height=1.0, size_pt=14, color=GREY, align=PP_ALIGN.CENTER,
    )

    # 6 SSIM components
    s = prs.slides.add_slide(blank)
    page_header(s, "SSIM：亮度 · 对比度 · 结构", "Structural Similarity · 不只比差，还比“像不像”")
    add_picture(s, figs["ssim_components"], 1.5, 2.5, 30.8)
    add_textbox(
        s,
        "三项都接近，分数才接近 1。对整体亮度偏移、对比度缩放通常比 MSE 更稳健。",
        left=1.8, top=16.5, width=30, height=1.0, size_pt=14, color=GREY, align=PP_ALIGN.CENTER,
    )

    # 7 SSIM scale
    s = prs.slides.add_slide(blank)
    page_header(s, "SSIM 分数长什么样？", "越接近 1，结构越“同款”")
    add_picture(s, figs["ssim_scale"], 1.5, 2.8, 30.8)
    add_textbox(
        s,
        "仓库实现是全局简化版（整块体积拉平后一次算），更像整体统计结构相似度，不是滑动窗口局部 SSIM。",
        left=1.8, top=15.8, width=30, height=1.8, size_pt=13, color=GREY, align=PP_ALIGN.CENTER,
    )

    # 8 comparison table
    s = prs.slides.add_slide(blank)
    page_header(s, "三指标对照：各管一摊事", "同一对体积，三种读法")
    headers = ["", "MSE", "PSNR", "SSIM"]
    rows = [
        ["一句话", "差多大", "相对峰值多干净", "结构像不像"],
        ["好方向", "↓ 越小越好", "↑ 越大越好", "↑ 越近 1 越好"],
        ["敏感点", "大误差、强度尺度", "与 MSE 同向", "模糊 / 形变 / 条纹"],
        ["比喻", "逐格对拍差", "分贝信噪尺", "同款鉴定"],
    ]
    add_rect(s, 1.6, 3.0, 30.5, 1.5, PRIMARY)
    col_w = [6.5, 8.0, 8.0, 8.0]
    x = 1.6
    for h, w in zip(headers, col_w):
        add_textbox(s, h, left=x, top=3.25, width=w, height=1.0, size_pt=16, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        x += w
    for ri, row in enumerate(rows):
        y = 4.6 + ri * 2.9
        add_rect(s, 1.6, y, 30.5, 2.8, LIGHT if ri % 2 == 0 else WHITE)
        x = 1.6
        for ci, (cell, w) in enumerate(zip(row, col_w)):
            add_textbox(
                s, cell, left=x + 0.2, top=y + 0.7, width=w - 0.4, height=1.4,
                size_pt=15, bold=(ci == 0), color=PRIMARY if ci == 0 else GREY, align=PP_ALIGN.CENTER,
            )
            x += w

    # 9 combo
    s = prs.slides.add_slide(blank)
    page_header(s, "怎么组合解读？", "像体检报告：单项 + 组合更靠谱")
    add_picture(s, figs["combo"], 4.5, 2.4, 24.8)

    # 10 pipeline
    s = prs.slides.add_slide(blank)
    page_header(s, "在 ET-benchmark 里怎么算", "对齐 → 再算指标（错位会伪装成算法很差）")
    stages = [("重建体积", "算法输出"), ("空间对齐", "贴合 GT 网格"), ("算三项指标", "MSE / PSNR / SSIM"), ("读报告", "组合解读")]
    for i, (t, b) in enumerate(stages):
        x = 1.8 + i * 7.8
        oval = s.shapes.add_shape(MSO_SHAPE.OVAL, Cm(x + 1.5), Cm(5.2), Cm(4.0), Cm(4.0))
        _set_fill(oval, PRIMARY if i < 3 else GOOD)
        _no_line(oval)
        add_textbox(s, str(i + 1), left=x + 1.5, top=6.2, width=4.0, height=1.8, size_pt=32, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
        add_textbox(s, t, left=x, top=9.8, width=7.0, height=0.9, size_pt=18, bold=True, align=PP_ALIGN.CENTER)
        add_textbox(s, b, left=x, top=10.8, width=7.0, height=0.8, size_pt=13, color=GREY, align=PP_ALIGN.CENTER)
    for i in range(3):
        x = 1.8 + i * 7.8 + 6.2
        ar = s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Cm(x), Cm(6.6), Cm(1.5), Cm(0.7))
        _set_fill(ar, ACCENT)
        _no_line(ar)
    add_textbox(s, "没有 GT 时这三项为空；配置 metrics 常见为 [psnr, ssim, mse]。", left=1.8, top=13.5, width=30, height=1.0, size_pt=14, color=GREY, align=PP_ALIGN.CENTER)

    # 11 takeaway
    s = prs.slides.add_slide(blank)
    add_rect(s, 0, 0, 33.87, 19.05, PRIMARY)
    add_textbox(s, "带走三句话", left=2, top=3.2, width=30, height=1.4, size_pt=36, bold=True, color=WHITE, align=PP_ALIGN.CENTER)
    for i, t in enumerate([
        "MSE：逐格对拍，差的平方平均 —— 越小越好",
        "PSNR：把 MSE 换成相对峰值的分贝尺 —— 越大越好",
        "SSIM：亮度 / 对比度 / 结构是否同款 —— 越近 1 越好",
    ]):
        add_textbox(s, t, left=3, top=6.0 + i * 2.1, width=28, height=1.5, size_pt=18, color=RGBColor(0xD0, 0xDC, 0xEE), align=PP_ALIGN.CENTER)
    add_textbox(s, "先对齐，再比较；三项一起看，比死盯一个数更稳。", left=3, top=14.5, width=28, height=1.2, size_pt=16, color=RGBColor(0xA8, 0xC0, 0xE0), align=PP_ALIGN.CENTER)

    return prs


def main():
    figs = make_figures()
    prs = build_pptx(figs)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(OUT))
    print(f"Saved: {OUT}")
    print(f"Figures: {FIG_DIR}")


if __name__ == "__main__":
    main()
