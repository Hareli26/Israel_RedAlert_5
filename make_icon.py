"""
Generates RedAlertIDF.icns using PyQt5 (already installed).
Run: python3 make_icon.py
"""
import os, sys, math, subprocess, shutil, tempfile

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import (QImage, QPainter, QColor, QFont, QPen,
                         QLinearGradient, QRadialGradient, QPainterPath)
from PyQt5.QtCore import Qt, QRectF, QPointF

app = QApplication(sys.argv)

SIZES = [16, 32, 64, 128, 256, 512, 1024]

def draw_icon(size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setRenderHint(QPainter.TextAntialiasing, True)

    s = size
    r = s * 0.12   # corner radius

    # ── background: dark rounded rect ──────────────────────────
    bg_path = QPainterPath()
    bg_path.addRoundedRect(QRectF(0, 0, s, s), r, r)

    grad = QLinearGradient(0, 0, 0, s)
    grad.setColorAt(0.0, QColor(12, 12, 28))
    grad.setColorAt(1.0, QColor(6, 6, 16))
    p.fillPath(bg_path, grad)

    # ── outer glow ring ─────────────────────────────────────────
    pen = QPen(QColor(180, 10, 10, 120))
    pen.setWidth(max(1, s // 80))
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(s*0.03, s*0.03, s*0.94, s*0.94), r*0.85, r*0.85)

    # ── alert triangle ─────────────────────────────────────────
    cx, cy = s * 0.5, s * 0.52
    th = s * 0.56   # triangle height
    tw = th * 1.12  # triangle base width
    tx, ty = cx, cy - th * 0.48  # tip

    tri = QPainterPath()
    tri.moveTo(tx, ty)
    tri.lineTo(cx - tw/2, cy + th*0.52)
    tri.lineTo(cx + tw/2, cy + th*0.52)
    tri.closeSubpath()

    tri_grad = QLinearGradient(0, ty, 0, cy + th*0.52)
    tri_grad.setColorAt(0.0, QColor(255, 60, 30))
    tri_grad.setColorAt(1.0, QColor(200, 0, 0))
    p.fillPath(tri, tri_grad)

    # triangle inner border highlight
    pen2 = QPen(QColor(255, 150, 100, 160))
    pen2.setWidth(max(1, s // 120))
    p.setPen(pen2)
    p.setBrush(Qt.NoBrush)
    p.drawPath(tri)

    # ── exclamation mark ────────────────────────────────────────
    font_size = max(8, int(s * 0.30))
    font = QFont("Arial", font_size, QFont.Bold)
    p.setFont(font)
    p.setPen(QColor(255, 255, 255, 240))
    # bar
    bar_h = int(s * 0.22)
    bar_w = max(2, int(s * 0.055))
    bar_x = int(cx - bar_w / 2)
    bar_y = int(cy - s * 0.20)
    p.fillRect(bar_x, bar_y, bar_w, bar_h, QColor(255, 255, 255, 235))
    # dot
    dot_r = max(2, int(s * 0.044))
    dot_x = int(cx - dot_r / 2)
    dot_y = int(cy + s * 0.07)
    p.fillRect(dot_x, dot_y, dot_r, dot_r, QColor(255, 255, 255, 235))

    p.end()
    return img


def save_icns(out_path="RedAlertIDF.icns"):
    tmpdir = tempfile.mkdtemp()
    iconset = os.path.join(tmpdir, "RedAlertIDF.iconset")
    os.makedirs(iconset)

    # iconutil naming: icon_SIZEx SIZE[@2x].png
    spec = [
        (16,  "icon_16x16.png"),
        (32,  "icon_16x16@2x.png"),
        (32,  "icon_32x32.png"),
        (64,  "icon_32x32@2x.png"),
        (128, "icon_128x128.png"),
        (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"),
        (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"),
        (1024,"icon_512x512@2x.png"),
    ]
    for sz, name in spec:
        img = draw_icon(sz)
        img.save(os.path.join(iconset, name), "PNG")
        print(f"  {sz}x{sz} → {name}")

    result = subprocess.run(
        ["iconutil", "-c", "icns", "-o", out_path, iconset],
        capture_output=True, text=True
    )
    shutil.rmtree(tmpdir)
    if result.returncode != 0:
        print("iconutil error:", result.stderr)
        return False
    print(f"Created: {out_path}")
    return True


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    save_icns("RedAlertIDF.icns")
    sys.exit(0)
