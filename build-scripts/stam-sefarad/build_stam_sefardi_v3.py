from __future__ import annotations

import json
import math
from pathlib import Path

import cv2
import numpy as np
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from PIL import Image, ImageDraw, ImageFont

SCRATCH = Path(__file__).resolve().parent / "scratch"
BRAIN = SCRATCH.parent
DESKEW_DIR = SCRATCH / "crops_27_deskewed"
MANIFEST_PATH = SCRATCH / "crops_27" / "targets_manifest.json"
MASK_DIR = SCRATCH / "masks_27_v3"
MASK_DIR.mkdir(parents=True, exist_ok=True)
OUTLINES_TTF = SCRATCH / "_stam_sefardi_v3_outlines.ttf"
TRACE_CHECK_PNG = BRAIN / "stam_sefardi_v3_trace_check.png"

UPEM = 2048

# 4 horizontal typographic guide lines (true 3-kulmus Sefardi proportion: 1 kulmus ~ 360u):
LINE_1_TOP_OUTER = 1115  # Top of main horizontal roof bar (top-left serifs poke above)
LINE_2_TOP_INNER = 755   # Bottom of main horizontal roof bar (360u thick)
LINE_3_BOT_INNER = 360   # Top of main horizontal base bar (360u thick)
LINE_4_BOT_OUTER = 0     # Bottom of main horizontal base bar (gimel leg, shin & samekh dip below)
BODY_H = LINE_1_TOP_OUTER
TARGET_BAR_U = LINE_1_TOP_OUTER - LINE_2_TOP_INNER  # 360u
STD_GRID_W = 925         # Standard 5/5 width for 5-column vertical grid (1/5=185u, 2/5=370u, 3/5=555u)

TAGIN_3 = {"gimel", "zayin", "tet", "nun", "finalnun", "ayin", "tsadi", "finaltsadi", "shin"}
TAGIN_1 = {"bet", "dalet", "he", "xet", "yod", "qof"}

# Letters whose flat/arched roof corner gets the ONE unified canonical top-left calligraphic serif (14 roofed letters)
CANONICAL_SERIF_14 = {
    "bet", "dalet", "he", "vav", "yod", "kaf", "finalkaf",
    "finalmem", "samekh", "pe", "finalpe", "qof", "resh", "tav",
}
CORNER_SERIF_TAGGED = {"bet", "dalet", "he", "qof"}
CORNER_SERIF_UNTAGGED = {"vav", "kaf", "finalkaf", "finalmem", "samekh", "pe", "finalpe", "resh", "tav", "mem"}

# Medium widths harmonized to a crisp 5-column vertical grid (5/5 = 925u, 2/5 = 370u for vav/zayin/yod/finalnun, 3/5 ~ 595-615u for gimel/nun)
TARGET_WIDTHS = {
    "alef":       935,
    "bet":        925,
    "gimel":      615,
    "dalet":      900,
    "he":         920,
    "vav":        370,
    "zayin":      380,
    "xet":        915,
    "tet":        945,
    "yod":        365,
    "kaf":        925,
    "finalkaf":   895,
    "lamed":      1075,
    "mem":        925,
    "finalmem":   910,
    "nun":        595,
    "finalnun":   385,
    "samekh":     915,
    "ayin":       925,
    "pe":         915,
    "finalpe":    855,
    "tsadi":      910,
    "finaltsadi": 895,
    "qof":        905,
    "resh":       925,
    "shin":       1205,
    "tav":        940,
}

# Target vertical anchor ranges (main_bot_y, main_top_y)
CALIBRATION = {
    "alef":       (0,    LINE_1_TOP_OUTER),
    "bet":        (0,    LINE_1_TOP_OUTER),
    "gimel":      (0,    LINE_1_TOP_OUTER),   # bot = flat left foot -> right leg dips < 0
    "dalet":      (0,    LINE_1_TOP_OUTER),
    "he":         (0,    LINE_1_TOP_OUTER),
    "vav":        (0,    LINE_1_TOP_OUTER),
    "zayin":      (0,    LINE_1_TOP_OUTER),
    "xet":        (0,    LINE_1_TOP_OUTER),   # top = main zayin heads -> chatoteret rises > 1115
    "tet":        (0,    LINE_1_TOP_OUTER),
    "yod":        (484,  LINE_1_TOP_OUTER),   # main flat roof sits at Line 1 (1115), underside at L2 (755) -> full 1 kulmus body
    "kaf":        (0,    LINE_1_TOP_OUTER),
    "finalkaf":   (-630, LINE_1_TOP_OUTER),
    "lamed":      (-18,  LINE_1_TOP_OUTER),   # special piecewise calibration: crossbar at Line 1..2, yMax ~1925
    "mem":        (0,    LINE_1_TOP_OUTER),   # top = right arch -> left crown serif pokes > 1115
    "finalmem":   (0,    LINE_1_TOP_OUTER),
    "nun":        (0,    LINE_1_TOP_OUTER),
    "finalnun":   (-610, LINE_1_TOP_OUTER),
    "samekh":     (0,    LINE_1_TOP_OUTER),
    "ayin":       (-265, LINE_1_TOP_OUTER),   # top = left zayin head -> right yod serif pokes > 1115
    "pe":         (-165, LINE_1_TOP_OUTER),
    "finalpe":    (-635, LINE_1_TOP_OUTER),
    "tsadi":      (-150, LINE_1_TOP_OUTER),
    "finaltsadi": (-610, LINE_1_TOP_OUTER),
    "qof":        (-580, LINE_1_TOP_OUTER),
    "resh":       (0,    LINE_1_TOP_OUTER),
    "shin":       (0,    LINE_1_TOP_OUTER),   # top = left square head, bot = main heel -> top serifs > 1115, bot serif < 0
    "tav":        (0,    LINE_1_TOP_OUTER),
}

# Gentle global stroke weight boosts on slender letters (preserving sharp tips & thick bars untouched)
THIN_DILATE = {
    "xet":        0.020,
    "zayin":      0.011,
    "finalnun":   0.011,
    "finaltsadi": 0.011,
    "shin":       0.009,
    "ayin":       0.009,
    "lamed":      0.005,
    "pe":         0.006,
    "finalpe":    0.005,
}


def estimate_paper_3x3(gray: np.ndarray) -> np.ndarray:
    h, w = gray.shape
    ys = np.linspace(0, h, 4, dtype=int)
    xs = np.linspace(0, w, 4, dtype=int)
    grid = np.zeros((3, 3), dtype=np.float32)
    for r in range(3):
        for c in range(3):
            blk = gray[ys[r]:ys[r + 1], xs[c]:xs[c + 1]]
            grid[r, c] = float(np.percentile(blk, 85)) if blk.size else 200.0
    paper = cv2.resize(grid, (w, h), interpolation=cv2.INTER_CUBIC)
    return np.clip(paper, 60.0, 255.0)


def _strip_raster_tagin_region(raw_sealed: np.ndarray, gname: str) -> np.ndarray:
    H2, W2 = raw_sealed.shape
    out = raw_sealed.copy()

    if gname == "tet":
        lx_end = int(W2 * 0.44)
        for y in range(int(H2 * 0.08), int(H2 * 0.55)):
            xs = np.where(out[y, :lx_end] > 0)[0]
            if len(xs) == 0:
                continue
            splits = np.where(np.diff(xs) > 4)[0]
            runs = np.split(xs, splits + 1)
            max_run = max(len(r) for r in runs)
            if len(runs) == 1 and max_run >= int(W2 * 0.14):
                next_ok = all(np.sum(out[min(H2 - 1, y + dy), xs[0]:xs[-1] + 1] > 0) >= max_run * 0.85 for dy in (6, 12, 18))
                if next_ok:
                    out[:max(0, y - 2), :lx_end] = 0
                    break
        return out

    if gname in ("zayin", "finalnun"):
        for y in range(int(H2 * 0.12), int(H2 * 0.55)):
            xs = np.where(out[y] > 0)[0]
            if len(xs) == 0:
                continue
            splits = np.where(np.diff(xs) > 4)[0]
            runs = np.split(xs, splits + 1)
            max_run = max(len(r) for r in runs)
            if max_run >= int(W2 * 0.34):
                r_big = max(runs, key=len)
                solid_down = all(np.sum(out[min(H2 - 1, y + dy), r_big[0]:r_big[-1] + 1] > 0) >= max_run * 0.85 for dy in (8, 16))
                if solid_down:
                    out[:max(0, y - 2), :] = 0
                    break
        return out

    if gname == "yod":
        row_widths = np.sum(out > 0, axis=1)
        band = row_widths[int(H2 * 0.22):int(H2 * 0.85)]
        if len(band) == 0:
            return out
        min_body_w = max(int(W2 * 0.32), int(band.max() * 0.65))
        y_shoulder = None
        for y in range(int(H2 * 0.22), int(H2 * 0.78) - 16):
            if np.all(row_widths[y:y + 16] >= min_body_w):
                y_shoulder = y
                break
        if y_shoulder is not None:
            sxs = np.where(out[y_shoulder + 12] > 0)[0]
            if len(sxs):
                x_left = int(sxs[0])
                body_w = int(sxs[-1] - sxs[0])
                cut_x0 = x_left + int(body_w * 0.34)
                out[:max(0, y_shoulder - 3), cut_x0:] = 0
        return out

    return out


def _seal_holes(mask: np.ndarray, gname: str) -> np.ndarray:
    out = mask.copy()
    cnts, hier = cv2.findContours(out, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    if hier is not None:
        holes = [(idx, cv2.contourArea(cnts[idx])) for idx, hi in enumerate(hier[0]) if hi[3] != -1]
        if holes:
            keep_idx = max(holes, key=lambda t: t[1])[0] if gname in ("finalmem", "samekh") else -1
            for idx, _ in holes:
                if idx != keep_idx:
                    cv2.drawContours(out, cnts, idx, 255, -1)
    return out


def _flatten_kaf_bottom(mask: np.ndarray) -> np.ndarray:
    """Flatten kaf's bottom horizontal base cleanly onto a level line while keeping its rounded right curve smooth."""
    out = mask.copy()
    H2, W2 = out.shape
    ys, xs = np.where(out > 0)
    if len(ys) == 0:
        return out
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    # Measure bottom-left corner level as flat reference
    left_bot_ys = []
    for x in range(bx0 + int(bw * 0.02), bx0 + int(bw * 0.22)):
        col_y = np.where(out[by0 + int(bh * 0.55):, x] > 0)[0]
        if len(col_y):
            left_bot_ys.append(by0 + int(bh * 0.55) + int(col_y[-1]))
    if not left_bot_ys:
        return out
    y_flat = int(np.percentile(left_bot_ys, 90))

    # Measure current bottom envelope per column across the base span [0..0.78*bw]
    dy_col = np.zeros(W2, dtype=np.float32)
    for x in range(bx0, bx0 + int(bw * 0.80)):
        col_y = np.where(out[by0 + int(bh * 0.52):, x] > 0)[0]
        if len(col_y):
            yb = by0 + int(bh * 0.52) + int(col_y[-1])
            diff = max(0.0, float(y_flat - yb))
            # Taper smoothly from x=0.52*bw to 0.80*bw into the rounded right back
            t_end = bx0 + bw * 0.80
            t_start = bx0 + bw * 0.52
            w_x = 1.0 if x <= t_start else max(0.0, (t_end - x) / max(1.0, t_end - t_start))
            dy_col[x] = diff * w_x

    # Smooth dy_col gently so there is zero kink
    dy_col = cv2.GaussianBlur(dy_col.reshape(1, -1), (1, 31), 6.0).ravel()

    # Warp ONLY bottom half pixels smoothly downward by w_y * dy_col[x]
    # w_y = 0 at y <= 0.42*bh (middle of hollow counter), rising to 1.0 by 0.60*bh (before bottom bar starts!)
    y_ramp0 = by0 + bh * 0.42
    y_ramp1 = by0 + bh * 0.60
    new_mask = np.zeros_like(out)
    map_y, map_x = np.meshgrid(np.arange(H2, dtype=np.float32), np.arange(W2, dtype=np.float32), indexing="ij")
    wy = np.clip((map_y - y_ramp0) / max(1.0, y_ramp1 - y_ramp0), 0.0, 1.0)
    src_y = map_y - wy * dy_col[None, :]
    new_mask = cv2.remap(out, map_x, src_y, interpolation=cv2.INTER_NEAREST, borderValue=0)
    return new_mask


def _reconstruct_serifs_geodesic(
    body_mask: np.ndarray, raw_sealed: np.ndarray, gname: str, k_open: int
) -> np.ndarray:
    """Safely reconstruct authentic razor-sharp corner serifs & bottom leg tips from raw_sealed
    without re-attaching separated callout lines or raster vertical tag stems."""
    H2, W2 = body_mask.shape
    ys_b, xs_b = np.where(body_mask > 0)
    if len(ys_b) == 0:
        return body_mask
    bx0, by0, bx1, by1 = int(xs_b.min()), int(ys_b.min()), int(xs_b.max()), int(ys_b.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    k_tip = 5 if gname in ("yod", "vav", "zayin", "finalnun", "finaltsadi") else 7
    tip_cand = cv2.morphologyEx(raw_sealed, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_tip, k_tip)))
    zone = np.zeros_like(body_mask)

    # 1. Lower-half sharp tips (bottom serifs & descender points)
    lower_y = by0 + int(bh * 0.46)
    zone[lower_y:, :] = 255

    # 2. Upper-half authentic serif ROIs (only for letters NOT replaced by CANONICAL_SERIF_14)
    upper_lim = by0 + int(bh * 0.40)
    if gname == "mem":
        zone[:upper_lim, : bx0 + int(bw * 0.24)] = 255
    elif gname == "alef":
        zone[:upper_lim, bx0 + int(bw * 0.52) :] = 255
    elif gname == "ayin":
        zone[:upper_lim, bx0 + int(bw * 0.50) :] = 255
    elif gname == "shin":
        # Middle & right pointed heads (keep left square head 3 tagin out!)
        zone[:upper_lim, bx0 + int(bw * 0.34) :] = 255
    elif gname == "tet":
        zone[:upper_lim, bx0 + int(bw * 0.44) :] = 255

    near_k = int(max(k_open, 15) * 2.2) | 1
    near_zone = cv2.dilate(body_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (near_k, near_k)))
    cand_masked = cv2.bitwise_and(tip_cand, cv2.bitwise_and(zone, near_zone))

    combined = cv2.bitwise_or(body_mask, cand_masked)
    n_c, lbl_c, _, _ = cv2.connectedComponentsWithStats(combined)
    # Keep ONLY connected components that physically overlap body_mask (true geodesic connectivity!)
    touch_labels = set(np.unique(lbl_c[body_mask > 0])) - {0}
    out = np.zeros_like(combined)
    for lid in touch_labels:
        out[lbl_c == lid] = 255
    return out


def _measure_mask_main_anchors(mask: np.ndarray, gname: str) -> tuple[float, float, float, float]:
    """Return (rx0, ry0_main, rx1, ry1_main) in y-up coordinates (img_h - y_img),
    excluding protruding serifs from ry0_main / ry1_main as specified per glyph."""
    H2, W2 = mask.shape
    ys, xs = np.where(mask > 0)
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    def y_up(y_img: float) -> float:
        return float(H2) - y_img

    # --- Top main line (in image y-down coords, then converted to y-up) ---
    y_top_img = float(by0)
    if gname == "kaf":
        mx0 = bx0 + int(bw * 0.20)
        mx1 = bx0 + int(bw * 0.48)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.32), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.32), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))
    elif gname in CORNER_SERIF_TAGGED or gname in ("finalkaf", "finalmem", "resh", "pe", "finalpe"):
        mx0 = bx0 + int(bw * 0.36)
        mx1 = bx0 + int(bw * 0.72)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.32), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.32), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))
    elif gname == "yod":
        # Main flat roof sits on Line 1 (1115) so canonical top-left serif pokes above Line 1
        mx0 = bx0 + int(bw * 0.38)
        mx1 = bx0 + int(bw * 0.62)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.36), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.36), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))
    elif gname == "vav":
        mx0 = bx0 + int(bw * 0.45)
        mx1 = bx0 + int(bw * 0.84)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.32), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.32), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))
    elif gname in ("samekh", "tav", "qof"):
        mx0 = bx0 + int(bw * 0.32)
        mx1 = bx0 + int(bw * 0.72)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.32), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.32), x] > 0)]
        if tops:
            # 15th percentile y_img = top of arched main roof, ignoring top-left corner serif
            y_top_img = float(np.percentile(tops, 15))
    elif gname == "alef":
        # Upper-left corner of main diagonal sits cleanly below top-right yod serif peak
        mx0 = bx0 + int(bw * 0.14)
        mx1 = bx0 + int(bw * 0.36)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.32), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.32), x] > 0)]
        if tops:
            y_top_img = float(np.percentile(tops, 12))
    elif gname == "xet":
        # Flat tops of left & right zayin heads, excluding center peaked chatoteret
        tops = []
        for lo, hi in ((0.06, 0.24), (0.76, 0.88)):
            for x in range(bx0 + int(bw * lo), bx0 + int(bw * hi)):
                col = np.where(mask[by0 + int(bh * 0.10):by0 + int(bh * 0.48), x] > 0)[0]
                if len(col):
                    tops.append(by0 + int(bh * 0.10) + int(col[0]))
        if tops:
            y_top_img = float(np.median(tops))
    elif gname == "mem":
        # Right arch of mem, letting left crown serif poke above Line 1
        mx0 = bx0 + int(bw * 0.50)
        mx1 = bx0 + int(bw * 0.82)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.35), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.35), x] > 0)]
        if tops:
            y_top_img = float(np.percentile(tops, 10))
    elif gname == "ayin":
        # Flat top of left square zayin head, letting right yod serif poke above Line 1
        mx0 = bx0 + int(bw * 0.08)
        mx1 = bx0 + int(bw * 0.34)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.35), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.35), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))
    elif gname == "shin":
        # Flat top of left square zayin head, letting middle & right pointed serifs poke above Line 1
        mx0 = bx0 + int(bw * 0.04)
        mx1 = bx0 + int(bw * 0.22)
        tops = [by0 + int(np.where(mask[by0:by0 + int(bh * 0.35), x] > 0)[0][0])
                for x in range(mx0, min(W2, mx1 + 1))
                if np.any(mask[by0:by0 + int(bh * 0.35), x] > 0)]
        if tops:
            y_top_img = float(np.median(tops))

    # --- Bottom main line (in image y-down coords) ---
    y_bot_img = float(by1)
    if gname == "gimel":
        # Flat bottom of left foot (letting pointed right leg dip below Line 4)
        lx0, lx1 = bx0, bx0 + int(bw * 0.48)
        bots = [by0 + int(bh * 0.50) + int(np.where(mask[by0 + int(bh * 0.50):, x] > 0)[0][-1])
                for x in range(lx0, lx1 + 1)
                if np.any(mask[by0 + int(bh * 0.50):, x] > 0)]
        if bots:
            y_bot_img = float(np.median(bots))
    elif gname == "shin":
        # Main base heel right of bottom-left pointed serif tip so bottom serif dips ~-55..-75u cleanly
        sx0, sx1 = bx0 + int(bw * 0.28), bx0 + int(bw * 0.48)
        bots = [by0 + int(bh * 0.50) + int(np.where(mask[by0 + int(bh * 0.50):, x] > 0)[0][-1])
                for x in range(sx0, sx1 + 1)
                if np.any(mask[by0 + int(bh * 0.50):, x] > 0)]
        if bots:
            y_bot_img = float(np.percentile(bots, 55))
    elif gname == "samekh":
        # Curved belly bottom sits on Line 4 (0) so pointed bottom-left corner dips cleanly ~-45..-60u (like shin)
        sx0, sx1 = bx0 + int(bw * 0.36), bx0 + int(bw * 0.56)
        bots = [by0 + int(bh * 0.55) + int(np.where(mask[by0 + int(bh * 0.55):, x] > 0)[0][-1])
                for x in range(sx0, sx1 + 1)
                if np.any(mask[by0 + int(bh * 0.55):, x] > 0)]
        if bots:
            y_bot_img = float(np.percentile(bots, 65))

    return float(bx0), y_up(y_bot_img), float(bx1), y_up(y_top_img)


def _align_kaf_4lines(mask: np.ndarray) -> np.ndarray:
    """1) Level kaf's bottom arm cleanly while preserving smooth back bend curve.
       2) Phase 1: globally map (top outer, top inner, bot inner, bot outer) to (1115 / 755 / 360 / 0).
       3) Phase 2: per-column straighten all 4 horizontal faces with smooth cosine blend into curved back.
       4) Phase 3: align vertical left ends of both arms cleanly."""
    out = _flatten_kaf_bottom(mask)
    H2, W2 = out.shape
    ys, xs = np.where(out > 0)
    if len(ys) == 0:
        return out
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    x_lo = bx0 + int(bw * 0.20)
    x_hi = bx0 + int(bw * 0.48)
    t1_list, t2_list, b1_list, b2_list = [], [], [], []
    y_mid = by0 + int(bh * 0.50)
    for x in range(x_lo, x_hi + 1):
        top_c = np.where(out[by0:y_mid, x] > 0)[0]
        bot_c = np.where(out[y_mid:by1 + 1, x] > 0)[0]
        if len(top_c) and len(bot_c):
            t1_list.append(by0 + int(top_c[0]))
            t2_list.append(by0 + int(top_c[-1]))
            b1_list.append(y_mid + int(bot_c[0]))
            b2_list.append(y_mid + int(bot_c[-1]))
    if not t1_list:
        return out
    y_t1 = float(np.median(t1_list))
    y_t2 = float(np.median(t2_list))
    y_b1 = float(np.median(b1_list))
    y_b2 = float(np.median(b2_list))
    H_bar = y_b2 - y_t1
    if H_bar < 20:
        return out

    tgt_t2 = y_t1 + (LINE_1_TOP_OUTER - LINE_2_TOP_INNER) / float(LINE_1_TOP_OUTER) * H_bar
    tgt_b1 = y_t1 + (LINE_1_TOP_OUTER - LINE_3_BOT_INNER) / float(LINE_1_TOP_OUTER) * H_bar

    dst_y = np.arange(H2, dtype=np.float32)
    src_y = dst_y.copy()
    m1 = (dst_y >= y_t1) & (dst_y <= tgt_t2)
    m2 = (dst_y > tgt_t2) & (dst_y <= tgt_b1)
    m3 = (dst_y > tgt_b1) & (dst_y <= y_b2)
    src_y[m1] = y_t1 + (dst_y[m1] - y_t1) * ((y_t2 - y_t1) / max(1.0, tgt_t2 - y_t1))
    src_y[m2] = y_t2 + (dst_y[m2] - tgt_t2) * ((y_b1 - y_t2) / max(1.0, tgt_b1 - tgt_t2))
    src_y[m3] = y_b1 + (dst_y[m3] - tgt_b1) * ((y_b2 - y_b1) / max(1.0, y_b2 - tgt_b1))

    map_y = np.broadcast_to(src_y[:, None], (H2, W2)).astype(np.float32)
    map_x = np.broadcast_to(np.arange(W2, dtype=np.float32)[None, :], (H2, W2))
    res1 = cv2.remap(out, map_x, map_y, interpolation=cv2.INTER_NEAREST, borderValue=0)

    # --- Phase 2: Per-column horizontal face straightening ---
    ys, xs = np.where(res1 > 0)
    if len(ys) == 0:
        return res1
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
    y_mid = int(round((tgt_t2 + tgt_b1) * 0.5))

    x_counter_end = bx0
    ym_lo = max(0, y_mid - 4)
    ym_hi = min(H2, y_mid + 5)
    for x in range(bx0 + int(bw * 0.20), bx1 + 1):
        if np.sum(res1[ym_lo:ym_hi, x] > 0) == 0:
            x_counter_end = x

    if x_counter_end > bx0 + int(bw * 0.25):
        span_xs = np.arange(bx0, x_counter_end + 1)
        n_sp = len(span_xs)
        t1_arr = np.full(n_sp, np.nan, dtype=np.float32)
        t2_arr = np.full(n_sp, np.nan, dtype=np.float32)
        b1_arr = np.full(n_sp, np.nan, dtype=np.float32)
        b2_arr = np.full(n_sp, np.nan, dtype=np.float32)
        for idx_k, x in enumerate(span_xs):
            tc = np.where(res1[by0:y_mid, x] > 0)[0]
            bc = np.where(res1[y_mid:by1 + 1, x] > 0)[0]
            if len(tc):
                t1_arr[idx_k] = by0 + float(tc[0])
                t2_arr[idx_k] = by0 + float(tc[-1])
            if len(bc):
                b1_arr[idx_k] = y_mid + float(bc[0])
                b2_arr[idx_k] = y_mid + float(bc[-1])

        ref_m = (span_xs >= bx0 + int(bw * 0.20)) & (span_xs <= bx0 + int(bw * 0.46)) & (~np.isnan(t1_arr)) & (~np.isnan(b2_arr))
        if np.any(ref_m):
            y_t1_flat = float(np.median(t1_arr[ref_m]))
            y_b2_flat = float(np.median(b2_arr[ref_m]))
            H_f = y_b2_flat - y_t1_flat
            y_t2_flat = y_t1_flat + (360.0 / 1115.0) * H_f
            y_b1_flat = y_t1_flat + ((1115.0 - 360.0) / 1115.0) * H_f

            for arr, fallback in ((t1_arr, y_t1_flat), (t2_arr, y_t2_flat), (b1_arr, y_b1_flat), (b2_arr, y_b2_flat)):
                valid = ~np.isnan(arr)
                if np.any(valid):
                    arr[:] = np.interp(span_xs, span_xs[valid], arr[valid]).astype(np.float32)
                else:
                    arr[:] = fallback
            t1_arr[span_xs < bx0 + int(bw * 0.16)] = y_t1_flat

            for arr in (t1_arr, t2_arr, b1_arr, b2_arr):
                arr[:] = cv2.GaussianBlur(arr.reshape(1, -1), (1, 15), 2.5, borderType=cv2.BORDER_REPLICATE).ravel()

            o0, o1 = bx0 + 0.52 * bw, bx0 + 0.68 * bw
            i0, i1 = bx0 + 0.56 * bw, min(bx0 + 0.70 * bw, float(x_counter_end - 6))
            map_y2 = np.broadcast_to(np.arange(H2, dtype=np.float32)[:, None], (H2, W2)).copy()
            ys_grid = np.arange(H2, dtype=np.float32)

            for idx_k, x in enumerate(span_xs):
                if x <= o0:
                    w_out = 1.0
                elif x < o1:
                    w_out = 0.5 * (1.0 + math.cos(math.pi * (x - o0) / max(1.0, o1 - o0)))
                else:
                    w_out = 0.0

                if x <= i0:
                    w_in = 1.0
                elif x < i1:
                    w_in = 0.5 * (1.0 + math.cos(math.pi * (x - i0) / max(1.0, i1 - i0)))
                else:
                    w_in = 0.0

                if (w_out <= 0.0 and w_in <= 0.0) or not (t2_arr[idx_k] < b1_arr[idx_k] - 4.0):
                    continue

                ot1 = float(t1_arr[idx_k])
                ot2 = float(t2_arr[idx_k])
                ob1 = float(b1_arr[idx_k])
                ob2 = float(b2_arr[idx_k])

                dt1 = w_out * y_t1_flat + (1.0 - w_out) * ot1
                dt2 = w_in * y_t2_flat + (1.0 - w_in) * ot2
                db1 = w_in * y_b1_flat + (1.0 - w_in) * ob1
                db2 = w_out * y_b2_flat + (1.0 - w_out) * ob2

                col_src = ys_grid.copy()
                r0 = ys_grid < dt1
                r1 = (ys_grid >= dt1) & (ys_grid <= dt2)
                r2 = (ys_grid > dt2) & (ys_grid <= db1)
                r3 = (ys_grid > db1) & (ys_grid <= db2)
                r4 = ys_grid > db2

                col_src[r0] = ys_grid[r0] + (ot1 - dt1)
                col_src[r1] = ot1 + (ys_grid[r1] - dt1) * ((ot2 - ot1) / max(1.0, dt2 - dt1))
                col_src[r2] = ot2 + (ys_grid[r2] - dt2) * ((ob1 - ot2) / max(1.0, db1 - dt2))
                col_src[r3] = ob1 + (ys_grid[r3] - db1) * ((ob2 - ob1) / max(1.0, db2 - db1))
                col_src[r4] = ys_grid[r4] + (ob2 - db2)
                map_y2[:, x] = col_src

            res2 = cv2.remap(res1, map_x, map_y2, interpolation=cv2.INTER_NEAREST, borderValue=0)

            # --- Phase 3: Align vertical left ends of both arms cleanly ---
            top_lxs, bot_lxs = [], []
            for y in range(max(0, int(round(y_t1_flat)) + 24), min(H2, int(round(y_t2_flat)) - 7)):
                rxs = np.where(res2[y, bx0 : bx0 + int(bw * 0.30)] > 0)[0]
                if len(rxs):
                    top_lxs.append(bx0 + int(rxs[0]))
            for y in range(max(0, int(round(y_b1_flat)) + 8), min(H2, int(round(y_b2_flat)) - 7)):
                rxs = np.where(res2[y, bx0 : bx0 + int(bw * 0.30)] > 0)[0]
                if len(rxs):
                    bot_lxs.append(bx0 + int(rxs[0]))
            if top_lxs and bot_lxs:
                x_l = int(round(max(float(np.median(top_lxs)), float(np.median(bot_lxs)))))
                res2[:, :x_l] = 0
                res2[max(0, int(round(y_t1_flat))) : min(H2, int(round(y_t2_flat)) + 1), x_l : min(W2, x_l + 18)] = 255
                res2[max(0, int(round(y_b1_flat))) : min(H2, int(round(y_b2_flat)) + 1), x_l : min(W2, x_l + 18)] = 255
            return res2

    return res1


def _balance_head_to_line2(mask: np.ndarray, gname: str) -> np.ndarray:
    """Smoothly map the bottom underside of vav, zayin, and finalnun's square heads to Line 2 (755u)
    while stretching the stem smoothly below to its baseline/descender target."""
    out = mask.copy()
    H2, W2 = out.shape
    ys, xs = np.where(out > 0)
    if len(ys) == 0:
        return out
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    if gname == "vav":
        roof_tops = [
            by0 + int(np.where(out[by0:by0 + int(bh * 0.30), x] > 0)[0][0])
            for x in range(bx0 + int(bw * 0.42), bx0 + int(bw * 0.84))
            if np.any(out[by0:by0 + int(bh * 0.30), x] > 0)
        ]
        if not roof_tops:
            return out
        y_roof = float(np.median(roof_tops))
        head_bots = []
        for x in range(bx0 + int(bw * 0.06), bx0 + int(bw * 0.42)):
            col = out[int(y_roof) : min(H2, by0 + int(bh * 0.65)), x]
            idx = np.where(col > 0)[0]
            if len(idx):
                s = idx[0]
                e = s
                while e + 1 < len(col) and col[e + 1] > 0:
                    e += 1
                if e < int(bh * 0.56):
                    head_bots.append(int(y_roof) + e)
        if not head_bots:
            return out
        y_head_bot = float(np.median(head_bots))
    else:
        # zayin & finalnun have flat horizontal tops across full head width -> find row where width narrows to neck
        y_roof = float(by0)
        row_w = np.array([int(np.sum(out[y, bx0 : bx1 + 1] > 0)) for y in range(by0, by1 + 1)])
        sample_end = min(len(row_w), max(10, int(bh * 0.14)))
        head_w = float(np.percentile(row_w[min(4, sample_end - 1) : sample_end], 90))
        y_head_bot = None
        for r_off in range(min(4, len(row_w) - 1), int(bh * 0.55)):
            if row_w[r_off] < head_w * 0.58:
                y_head_bot = float(by0 + r_off - 1)
                break
        if y_head_bot is None:
            return out

    t_y0, t_y1 = CALIBRATION[gname]
    target_ratio = TARGET_BAR_U / max(1.0, float(t_y1 - t_y0))
    cur_ratio = (y_head_bot - y_roof) / max(1.0, float(by1) - y_roof)
    if abs(cur_ratio - target_ratio) <= 0.004:
        return out

    y_target_bot = y_roof + target_ratio * (float(by1) - y_roof)
    dst_y = np.arange(H2, dtype=np.float32)
    src_y = dst_y.copy()
    mask_head = (dst_y > y_roof) & (dst_y <= y_target_bot)
    mask_leg = (dst_y > y_target_bot) & (dst_y <= by1)
    src_y[mask_head] = y_roof + (dst_y[mask_head] - y_roof) * ((y_head_bot - y_roof) / max(1.0, y_target_bot - y_roof))
    src_y[mask_leg] = y_head_bot + (dst_y[mask_leg] - y_target_bot) * ((float(by1) - y_head_bot) / max(1.0, float(by1) - y_target_bot))

    map_y = np.broadcast_to(src_y[:, None], (H2, W2)).astype(np.float32)
    map_x = np.broadcast_to(np.arange(W2, dtype=np.float32)[None, :], (H2, W2))
    return cv2.remap(out, map_x, map_y, interpolation=cv2.INTER_NEAREST, borderValue=0)


def _balance_xet_heads(mask: np.ndarray) -> np.ndarray:
    """Smoothly map the bottom underside of xet's two main zayin heads cleanly to Line 2 (755u)
    while preserving the peaked chatoteret arch above Line 1 (1115) intact."""
    out = mask.copy()
    H2, W2 = out.shape
    ys, xs = np.where(out > 0)
    if len(ys) == 0:
        return out
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    # Top of left & right heads
    head_tops = []
    for lo, hi in ((0.06, 0.24), (0.76, 0.88)):
        for x in range(bx0 + int(bw * lo), bx0 + int(bw * hi)):
            col = np.where(out[by0 + int(bh * 0.10) : by0 + int(bh * 0.48), x] > 0)[0]
            if len(col):
                head_tops.append(by0 + int(bh * 0.10) + int(col[0]))
    if not head_tops:
        return out
    y_heads_top = float(np.median(head_tops))

    # Bottom flat underside of left & right square head boxes
    head_bots = []
    for x0f, x1f in ((0.04, 0.34), (0.66, 0.96)):
        x_a, x_b = bx0 + int(bw * x0f), bx0 + int(bw * x1f)
        rw_scan = [int(np.sum(out[y, x_a : x_b + 1] > 0)) for y in range(int(y_heads_top) + 4, by0 + int(bh * 0.65))]
        if len(rw_scan) < 12:
            continue
        box_w = float(np.percentile(rw_scan[2 : min(20, len(rw_scan))], 90))
        for k, wv in enumerate(rw_scan[4:], start=4):
            if wv < box_w * 0.55:
                head_bots.append(int(y_heads_top) + 4 + k - 1)
                break
    if not head_bots:
        return out
    y_heads_bot = float(np.median(head_bots))

    target_ratio = TARGET_BAR_U / float(LINE_1_TOP_OUTER)  # 360 / 1115
    cur_ratio = (y_heads_bot - y_heads_top) / max(1.0, float(by1) - y_heads_top)
    if abs(cur_ratio - target_ratio) <= 0.002:
        return out

    y_target_bot = y_heads_top + target_ratio * (float(by1) - y_heads_top)
    dst_y = np.arange(H2, dtype=np.float32)
    src_y = dst_y.copy()
    mask_head = (dst_y > y_heads_top) & (dst_y <= y_target_bot)
    mask_legs = (dst_y > y_target_bot) & (dst_y <= by1)
    src_y[mask_head] = y_heads_top + (dst_y[mask_head] - y_heads_top) * ((y_heads_bot - y_heads_top) / max(1.0, y_target_bot - y_heads_top))
    src_y[mask_legs] = y_heads_bot + (dst_y[mask_legs] - y_target_bot) * ((float(by1) - y_heads_bot) / max(1.0, float(by1) - y_target_bot))

    map_y = np.broadcast_to(src_y[:, None], (H2, W2)).astype(np.float32)
    map_x = np.broadcast_to(np.arange(W2, dtype=np.float32)[None, :], (H2, W2))
    return cv2.remap(out, map_x, map_y, interpolation=cv2.INTER_NEAREST, borderValue=0)


def _apply_canonical_topleft_serif(
    mask: np.ndarray, gname: str, y_roof_img: float, scale_x: float, scale_y: float
) -> np.ndarray:
    """Replace each of the 14 roofed left-serif letters' uneven raw top-left corner spur
    with ONE identical, smooth concave calligraphic Sefardi serif (+82u above Line 1)."""
    if gname not in CANONICAL_SERIF_14:
        return mask

    out = mask.copy()
    H2, W2 = out.shape
    ys, xs = np.where(out > 0)
    if len(ys) == 0:
        return out
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    is_pe = gname in ("pe", "finalpe")
    h_u = 210.0 if is_pe else 82.0
    h_px = max(6.0, h_u / max(1e-4, scale_y))
    w_u = 72.0 if gname in ("vav", "yod") else (90.0 if is_pe else 92.0)
    w_px = max(8.0, w_u / max(1e-4, scale_x))

    # Measure clean vertical left edge just below the corner serif flare
    y_scan0 = int(np.clip(y_roof_img + max(4.0, bh * 0.04), 0, H2 - 1))
    y_scan1 = int(np.clip(y_roof_img + max(10.0, bh * 0.14), y_scan0 + 2, H2))
    left_xs = []
    for y in range(y_scan0, y_scan1):
        row_xs = np.where(out[y, bx0 : bx0 + int(bw * 0.35)] > 0)[0]
        if len(row_xs):
            left_xs.append(bx0 + int(row_xs[0]))
    x_left = int(round(np.median(left_xs))) if left_xs else bx0

    # Measure exact roof height right where the serif's right foot attaches
    if gname == "yod":
        y_join = int(round(y_roof_img))
    else:
        jx0 = int(np.clip(x_left + w_px * 1.02, x_left + 4, bx1 - 2))
        jx1 = int(np.clip(x_left + w_px * 1.55, jx0 + 3, bx1))
        join_tops = []
        scan_t0 = max(0, int(y_roof_img - bh * 0.14))
        scan_t1 = min(H2, int(y_roof_img + bh * 0.20))
        for x in range(jx0, jx1 + 1):
            col = np.where(out[scan_t0:scan_t1, x] > 0)[0]
            if len(col):
                join_tops.append(scan_t0 + int(col[0]))
        y_join = int(round(np.median(join_tops))) if join_tops else int(round(y_roof_img))

    # 1. Trim old uneven spur above y_join in the left corner zone ONLY
    clear_end = min(bx1 - 4, bx0 + int(bw * 0.45)) if gname == "yod" else min(bx0 + int(bw * 0.32), int(round(x_left + w_px * 1.32)))
    out[:y_join, :clear_end] = 0

    # 2. Trim any tiny ragged pixels sticking left of x_left in the upper-left corner band
    y_top_band0 = max(0, int(round(y_join - h_px)) - 6)
    out[:y_scan1, :x_left] = 0

    # 3. Guarantee solid ink backing just beneath [x_left .. x_left + w_px] so no hollow seam exists
    x_rfoot = int(round(x_left + w_px))
    out[y_join : min(H2, y_join + 10), x_left : min(W2, x_rfoot + 1)] = 255

    # 4. Rasterize smooth canonical quadratic-Bezier Sefardi serif above y_join
    ts = np.linspace(0.0, 1.0, 28)
    if is_pe:
        # Prominent tall Sefardi oketz (עוקץ על פניה) with crisp 12u calligraphic nib tip for 10pt legibility
        tip_w = max(1.5, 12.0 / max(1e-4, scale_x))
        p0_l = np.array([float(x_left), float(y_join) - h_px])
        p0_r = np.array([float(x_left) + tip_w, float(y_join) - h_px + 0.03 * h_px])
        p1 = np.array([float(x_left) + 0.32 * w_px, float(y_join) - 0.22 * h_px])
        p2 = np.array([float(x_left) + w_px, float(y_join)])
        curve = ((1.0 - ts) ** 2)[:, None] * p0_r + (2.0 * (1.0 - ts) * ts)[:, None] * p1 + (ts ** 2)[:, None] * p2
        poly = np.vstack([
            [p0_l],
            curve,
            [[float(x_left) + w_px, float(y_join) + 6.0], [float(x_left), float(y_join) + 6.0]],
        ])
    else:
        p0 = np.array([float(x_left), float(y_join) - h_px])
        p1 = np.array([float(x_left) + 0.24 * w_px, float(y_join) - 0.14 * h_px])
        p2 = np.array([float(x_left) + w_px, float(y_join)])
        curve = ((1.0 - ts) ** 2)[:, None] * p0 + (2.0 * (1.0 - ts) * ts)[:, None] * p1 + (ts ** 2)[:, None] * p2
        poly = np.vstack([
            curve,
            [[float(x_left) + w_px, float(y_join) + 6.0], [float(x_left), float(y_join) + 6.0]],
        ])
    poly_s4 = np.round(poly * 16.0).astype(np.int32)
    cv2.fillPoly(out, [poly_s4], 255, shift=4)
    return out


def _harmonize_bars_and_weight(mask: np.ndarray, gname: str) -> np.ndarray:
    """1) Smoothly balance xet/vav/zayin/finalnun heads & align kaf's 4 horizontal planes.
       2) Gentle global dilation on slender letters.
       3) Artifact-free 1D vertical erosion ONLY when bars exceed TARGET_BAR_U + 18u (~378u).
       4) Unified canonical top-left serif across all 14 roofed left-serif letters."""
    out = mask.copy()

    # Step A: Slender-letter gentle dilation FIRST so subsequent head-to-Line-2 alignment is exact
    dil_f = THIN_DILATE.get(gname, 0.0)
    if dil_f > 0:
        ys, _ = np.where(out > 0)
        bh = max(1, int(ys.max()) - int(ys.min()))
        r = max(1, int(round(dil_f * bh)))
        out = cv2.dilate(out, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        out = _seal_holes(out, gname)

    # Step B: Head-to-Line-2 alignment AFTER dilation
    if gname in ("vav", "zayin", "finalnun"):
        out = _balance_head_to_line2(out, gname)
    elif gname == "xet":
        out = _balance_xet_heads(out)

    # Step C: Lock kaf cleanly to all 4 horizontal guide lines (1115 / 755 / 360 / 0)
    if gname == "kaf":
        out = _align_kaf_4lines(out)

    H2, W2 = out.shape
    rx0, ry0_m, rx1, ry1_m = _measure_mask_main_anchors(out, gname)
    t_y0, t_y1 = CALIBRATION[gname]
    if gname == "lamed":
        ys, xs = np.where(out > 0)
        bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        scale_y = 1133.0 / max(1.0, (by1 - by0) * 0.50)
    else:
        scale_y = (t_y1 - t_y0) / max(1.0, ry1_m - ry0_m)

    ys, xs = np.where(out > 0)
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    # Fill tiny paper-grain surface flecks on qof roof before serif splicing
    if gname == "qof":
        out = cv2.morphologyEx(out, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
        out = _seal_holes(out, gname)

    # Step D: Smooth artifact-free 1D vertical erosion ONLY when a bar exceeds TARGET_BAR_U (360u) by > 18u
    HEAVY_BOX_ERODE = {"bet", "finalmem", "tet"}
    HEAVY_ROOF_ERODE = {"finalkaf", "resh"}
    if gname in HEAVY_BOX_ERODE or gname in HEAVY_ROOF_ERODE:
        y_top_m_img = int(round(H2 - ry1_m))
        roof_runs = []
        x_lo = bx0 + int(bw * (0.28 if gname not in ("resh", "finalkaf") else 0.14))
        x_hi = bx0 + int(bw * (0.72 if gname not in ("resh", "finalkaf") else 0.64))
        for x in range(x_lo, x_hi):
            col = out[max(0, y_top_m_img) : min(H2, y_top_m_img + int(bh * 0.42)), x]
            idx = np.where(col > 0)[0]
            if len(idx):
                s = idx[0]
                e = s
                while e + 1 < len(col) and col[e + 1] > 0:
                    e += 1
                if e + 8 < len(col) and np.sum(col[e + 1 : e + 9]) == 0:
                    roof_runs.append(e - s + 1)
        if roof_runs:
            th_px = float(np.median(roof_runs))
            excess_u = th_px * scale_y - TARGET_BAR_U
            if excess_u > 18.0:
                r = max(1, min(4, int(round((excess_u / scale_y) * 0.45))))
                vker = np.ones((2 * r + 1, 1), dtype=np.uint8)
                eroded_v = cv2.erode(out, vker)
                if gname in HEAVY_BOX_ERODE:
                    out = _seal_holes(eroded_v, gname)
                else:
                    cut_y = by0 + int(bh * 0.68)
                    merged = out.copy()
                    merged[:cut_y, :] = eroded_v[:cut_y, :]
                    out = _seal_holes(merged, gname)

    # Re-measure anchors after erosion and splice ONE unified canonical top-left serif onto all 14 roofed letters
    if gname in CANONICAL_SERIF_14:
        rx0, ry0_m, rx1, ry1_m = _measure_mask_main_anchors(out, gname)
        t_y0, t_y1 = CALIBRATION[gname]
        scale_y = (t_y1 - t_y0) / max(1.0, ry1_m - ry0_m)
        scale_x_raw = float(TARGET_WIDTHS[gname]) / max(1.0, rx1 - rx0)
        scale_x = max(0.76 * scale_y, min(1.32 * scale_y, scale_x_raw))
        out = _apply_canonical_topleft_serif(out, gname, float(H2) - ry1_m, scale_x, scale_y)

    return out


def extract_clean_mask(crop_bgr: np.ndarray, gname: str) -> np.ndarray:
    if gname == "kaf":
        return _render_kaf_perfect_mask()
    gray = cv2.cvtColor(crop_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    paper = estimate_paper_3x3(gray)
    dark = (paper - gray.astype(np.float32)) / np.maximum(paper, 60.0)

    cy0, cy1 = int(h * 0.14), int(h * 0.88)
    cx0, cx1 = int(w * 0.12), int(w * 0.88)
    roi_u8 = np.clip(dark[cy0:cy1, cx0:cx1] * 255.0, 0, 255).astype(np.uint8)
    otsu_val, _ = cv2.threshold(roi_u8, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh = max(0.32, min(0.48, (otsu_val / 255.0) * 0.90))

    sc = 2
    dark2 = cv2.resize(dark, (w * sc, h * sc), interpolation=cv2.INTER_CUBIC)
    raw = (dark2 >= thresh).astype(np.uint8) * 255
    H2, W2 = raw.shape

    rim_x = max(4, int(W2 * (0.022 if gname != "zayin" else 0.0)))
    rim_y = max(4, int(H2 * 0.020))
    raw[:rim_y, :] = 0
    raw[-rim_y:, :] = 0
    if rim_x > 0:
        raw[:, :rim_x] = 0
    raw[:, -max(4, int(W2 * 0.022)):] = 0
    if gname == "finalpe":
        raw[int(H2 * 0.925):, :] = 0

    k_seal = 3 if gname in ("zayin", "xet", "yod", "finalnun") else 9
    raw_sealed = cv2.morphologyEx(raw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_seal, k_seal)))
    raw_sealed = _strip_raster_tagin_region(raw_sealed, gname)

    min_dim = min(W2, H2)
    if gname == "xet":
        k_open = max(5, min(7, int(min_dim * 0.006) | 1))
    elif gname == "lamed":
        k_open = max(5, min(9, int(min_dim * 0.010) | 1))
    elif gname == "yod":
        k_open = max(5, min(9, int(min_dim * 0.012) | 1))
    else:
        k_open = max(11, min(31, int(min_dim * 0.024) | 1))
    opened = cv2.morphologyEx(raw_sealed, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k_open, k_open)))

    if gname == "xet":
        lx_end_tag = int(W2 * 0.335)
        y_lhead = None
        for y in range(int(H2 * 0.16), int(H2 * 0.48)):
            xs = np.where(opened[y, :int(W2 * 0.40)] > 0)[0]
            if len(xs) >= int(W2 * 0.14):
                y_lhead = y
                break
        if y_lhead is not None:
            opened[:max(0, y_lhead - 2), :lx_end_tag] = 0
        n_x, lbl_x, st_x, _ = cv2.connectedComponentsWithStats(opened)
        mx_area = max([st_x[i, cv2.CC_STAT_AREA] for i in range(1, n_x)], default=1)
        clean4 = np.zeros_like(opened)
        for i in range(1, n_x):
            if st_x[i, cv2.CC_STAT_AREA] >= mx_area * 0.035:
                clean4[lbl_x == i] = 255
        clean4 = cv2.morphologyEx(clean4, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21)))
        fine = (dark2 >= 0.30).astype(np.uint8) * 255
        if y_lhead is not None:
            fine[:max(0, y_lhead - 2), :lx_end_tag] = 0
        pinch_mask = np.zeros_like(clean4)
        pinch_mask[int(H2 * 0.16):int(H2 * 0.37), int(W2 * 0.32):int(W2 * 0.65)] = 255
        pinch_mask[int(H2 * 0.44):int(H2 * 0.56), int(W2 * 0.21):int(W2 * 0.29)] = 255
        pinch_mask[int(H2 * 0.44):int(H2 * 0.56), int(W2 * 0.62):int(W2 * 0.71)] = 255
        bridge_fill = cv2.dilate(cv2.bitwise_and(fine, pinch_mask), cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
        opened = cv2.bitwise_or(clean4, cv2.bitwise_and(bridge_fill, pinch_mask))
        opened = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (19, 19)))

    n_o, lbl_o, st_o, cent_o = cv2.connectedComponentsWithStats(opened)
    if n_o <= 1:
        return raw_sealed

    cands = []
    for i in range(1, n_o):
        x, y, bw, bh, area = [int(v) for v in st_o[i]]
        cx_c, cy_c = cent_o[i]
        if (x <= W2 * 0.03 or x + bw >= W2 * 0.97) and area < W2 * H2 * 0.04:
            continue
        cands.append((area, i, x, y, bw, bh, cx_c, cy_c))
    if not cands:
        for i in range(1, n_o):
            x, y, bw, bh, area = [int(v) for v in st_o[i]]
            cands.append((area, i, x, y, bw, bh, cent_o[i][0], cent_o[i][1]))
    cands.sort(reverse=True)
    largest_area = cands[0][0]
    main_x, main_y, main_w, main_h = cands[0][2], cands[0][3], cands[0][4], cands[0][5]
    pad_bx, pad_by = int(W2 * 0.30), int(H2 * 0.38)
    body_mask = np.zeros_like(opened)
    for area, i, x, y, bw, bh, cx_c, cy_c in cands:
        if i != cands[0][1] and (y + bh) <= main_y + 15 and area < largest_area * 0.25:
            continue
        if i != cands[0][1] and (y + bh) < H2 * 0.14 and area < largest_area * 0.15:
            continue
        near_main = (
            main_x - pad_bx <= cx_c <= main_x + main_w + pad_bx
            and main_y - pad_by <= cy_c <= main_y + main_h + pad_by
        )
        min_frac = 0.048 if gname != "xet" else 0.035
        if area >= max(220, largest_area * min_frac) and (near_main or area >= largest_area * 0.16):
            body_mask[lbl_o == i] = 255

    # Reconstruct BOTH lower tips AND upper corner serifs cleanly without callouts/tagin!
    reconstructed = _reconstruct_serifs_geodesic(body_mask, raw_sealed, gname, k_open)

    n_f, lbl_f, st_f, _ = cv2.connectedComponentsWithStats(reconstructed)
    final_mask = np.zeros_like(reconstructed)
    min_frac_f = 0.048 if gname != "xet" else 0.035
    for i in range(1, n_f):
        if st_f[i, cv2.CC_STAT_AREA] >= max(220, largest_area * min_frac_f):
            final_mask[lbl_f == i] = 255

    if gname not in ("zayin", "xet", "yod"):
        final_mask = cv2.morphologyEx(final_mask, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)))
    final_mask = _seal_holes(final_mask, gname)
    return _harmonize_bars_and_weight(final_mask, gname)


# --- Smooth Bezier fitting (strict handle clamp) ---

def _q_bezier_err(pts: np.ndarray, ctrl: list[np.ndarray], t: np.ndarray) -> tuple[float, int]:
    p0, p1, p2, p3 = ctrl
    mt = 1.0 - t
    curve = (
        (mt ** 3)[:, None] * p0
        + (3 * (mt ** 2) * t)[:, None] * p1
        + (3 * mt * (t ** 2))[:, None] * p2
        + (t ** 3)[:, None] * p3
    )
    dists = np.linalg.norm(pts - curve, axis=1)
    idx = int(np.argmax(dists))
    return float(dists[idx]), idx


def _chord_params(pts: np.ndarray) -> np.ndarray:
    diffs = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    u = np.concatenate([[0.0], np.cumsum(diffs)])
    if u[-1] > 1e-6:
        u /= u[-1]
    return u


def _generate_bezier(pts: np.ndarray, u: np.ndarray, t0: np.ndarray, t1: np.ndarray) -> list[np.ndarray]:
    p0, p3 = pts[0], pts[-1]
    if len(pts) <= 2:
        dist = np.linalg.norm(p3 - p0) / 3.0
        return [p0, p0 + t0 * dist, p3 + t1 * dist, p3]
    mt = 1.0 - u
    a1 = 3 * (mt ** 2)[:, None] * u[:, None] * t0[None, :]
    a2 = 3 * mt[:, None] * (u ** 2)[:, None] * t1[None, :]
    c = np.zeros((2, 2))
    x = np.zeros(2)
    b0 = (mt ** 3 + 3 * (mt ** 2) * u)[:, None] * p0
    b1 = (3 * mt * (u ** 2) + u ** 3)[:, None] * p3
    rhs = pts - b0 - b1
    c[0, 0] = float(np.sum(a1 * a1))
    c[0, 1] = float(np.sum(a1 * a2))
    c[1, 0] = c[0, 1]
    c[1, 1] = float(np.sum(a2 * a2))
    x[0] = float(np.sum(a1 * rhs))
    x[1] = float(np.sum(a2 * rhs))
    det = c[0, 0] * c[1, 1] - c[0, 1] * c[1, 0]
    seg_len = float(np.linalg.norm(p3 - p0))
    alpha_l = alpha_r = seg_len / 3.0
    if abs(det) > 1e-9:
        al = (x[0] * c[1, 1] - x[1] * c[0, 1]) / det
        ar = (c[0, 0] * x[1] - c[1, 0] * x[0]) / det
        if 1e-3 < al < seg_len * 0.55 and 1e-3 < ar < seg_len * 0.55:
            alpha_l, alpha_r = al, ar
    return [p0, p0 + t0 * alpha_l, p3 + t1 * alpha_r, p3]


def _fit_cubic(pts: np.ndarray, t0: np.ndarray, t1: np.ndarray, max_err: float, depth: int = 0) -> list[list[np.ndarray]]:
    n = len(pts)
    if n == 2:
        dist = np.linalg.norm(pts[1] - pts[0]) / 3.0
        return [[pts[0], pts[0] + t0 * dist, pts[1] + t1 * dist, pts[1]]]
    u = _chord_params(pts)
    ctrl = _generate_bezier(pts, u, t0, t1)
    err, split = _q_bezier_err(pts, ctrl, u)
    if err <= max_err or depth >= 8 or n <= 4:
        return [ctrl]
    tan = pts[min(n - 1, split + 2)] - pts[max(0, split - 2)]
    norm = np.linalg.norm(tan)
    t_mid = tan / norm if norm > 1e-6 else t0
    return _fit_cubic(pts[:split + 1], t0, -t_mid, max_err, depth + 1) + _fit_cubic(pts[split:], t_mid, t1, max_err, depth + 1)


def _detect_corners(pts: np.ndarray, step: int = 8, angle_deg: float = 34.0) -> list[int]:
    n = len(pts)
    if n < 2 * step + 2:
        return list(range(n))
    angles = np.zeros(n)
    for i in range(n):
        v1 = pts[i] - pts[(i - step) % n]
        v2 = pts[(i + step) % n] - pts[i]
        n1, n2 = np.linalg.norm(v1), np.linalg.norm(v2)
        if n1 < 1e-4 or n2 < 1e-4:
            continue
        cos_a = np.clip(np.dot(v1, v2) / (n1 * n2), -1.0, 1.0)
        angles[i] = math.degrees(math.acos(cos_a))
    win = max(5, step)
    corners = []
    for i in range(n):
        if angles[i] < angle_deg:
            continue
        is_peak = True
        for k in range(-win, win + 1):
            if k != 0 and angles[(i + k) % n] > angles[i] + (1e-5 if k < 0 else 0.0):
                is_peak = False
                break
        if is_peak:
            if not corners or (i - corners[-1]) > win:
                corners.append(i)
    if not corners:
        corners = [0, n // 2]
    return corners


def contour_to_cubics(cnt_xy: np.ndarray, is_hole: bool, smooth_sigma: float = 2.0, max_err: float = 2.4) -> list[tuple]:
    pts = cnt_xy.astype(np.float64)
    closed = np.vstack([pts, pts[0]])
    seglens = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.concatenate([[0.0], np.cumsum(seglens)])
    total_len = cum[-1]
    if total_len < 8.0:
        return []
    n_samp = max(24, int(round(total_len / 1.5)))
    s_grid = np.linspace(0, total_len, n_samp, endpoint=False)
    pts = np.column_stack([np.interp(s_grid, cum, closed[:, 0]), np.interp(s_grid, cum, closed[:, 1])])

    corners = _detect_corners(pts, step=max(5, int(min(10, total_len * 0.03))), angle_deg=30.0)
    ops = []
    for idx_c in range(len(corners)):
        c0 = corners[idx_c]
        c1 = corners[(idx_c + 1) % len(corners)]
        seg = pts[c0:c1 + 1].copy() if c1 > c0 else np.vstack([pts[c0:], pts[:c1 + 1]])
        if len(seg) < 2:
            continue
        p_start, p_end = seg[0], seg[-1]
        v = p_end - p_start
        vlen = np.linalg.norm(v)
        if vlen < 1e-4:
            continue
        perp = np.abs((seg[:, 0] - p_start[0]) * v[1] - (seg[:, 1] - p_start[1]) * v[0]) / vlen
        if len(seg) <= 5 or np.max(perp) <= 1.8:
            if not ops:
                ops.append(("moveTo", (tuple(p_start),)))
            ops.append(("lineTo", (tuple(p_end),)))
            continue

        if smooth_sigma > 0 and len(seg) > 7:
            k_r = int(smooth_sigma * 2) + 1
            pad = np.vstack([np.repeat(seg[:1], k_r, axis=0), seg, np.repeat(seg[-1:], k_r, axis=0)])
            g1d = cv2.getGaussianKernel(2 * k_r + 1, smooth_sigma).ravel()
            seg[1:-1, 0] = np.convolve(pad[:, 0], g1d, mode="valid")[1:-1]
            seg[1:-1, 1] = np.convolve(pad[:, 1], g1d, mode="valid")[1:-1]

        t0 = seg[min(3, len(seg) - 1)] - seg[0]
        t0 /= max(1e-6, np.linalg.norm(t0))
        t1 = seg[-min(4, len(seg))] - seg[-1]
        t1 /= max(1e-6, np.linalg.norm(t1))
        cubics = _fit_cubic(seg, t0, t1, max_err=max_err)
        if not ops:
            ops.append(("moveTo", (tuple(cubics[0][0]),)))
        for c in cubics:
            ops.append(("curveTo", (tuple(c[1]), tuple(c[2]), tuple(c[3]))))
    if ops:
        ops.append(("closePath", ()))
    return ops


def _lamed_piecewise_y(pts: np.ndarray, bar_top_up: float, bar_bot_up: float, bot_up: float, head_top_up: float) -> np.ndarray:
    """For lamed: 3-segment smooth vertical map pinning middle crossbar cleanly between LINE_1 (1115) & LINE_2 (755),
    bottom tip at -18, and upper head top at ~1925."""
    target_bar_top = float(LINE_1_TOP_OUTER)  # 1115
    target_bar_bot = float(LINE_2_TOP_INNER)  # 755
    target_bot = -18.0
    target_head_top = 1925.0

    sc_bot = (target_bar_bot - target_bot) / max(1.0, bar_bot_up - bot_up)
    sc_bar = (target_bar_top - target_bar_bot) / max(1.0, bar_top_up - bar_bot_up)
    sc_top = (target_head_top - target_bar_top) / max(1.0, head_top_up - bar_top_up)

    y = pts[:, 1]
    y_new = np.where(
        y <= bar_bot_up,
        target_bot + (y - bot_up) * sc_bot,
        np.where(
            y <= bar_top_up,
            target_bar_bot + (y - bar_bot_up) * sc_bar,
            target_bar_top + (y - bar_top_up) * sc_top,
        ),
    )
    return np.column_stack([pts[:, 0], y_new])


TOP_L2_WINDOWS: dict[str, list[tuple[float, float]]] = {
    "bet":        [(0.25, 0.60)],
    "gimel":      [(0.05, 0.30)],
    "dalet":      [(0.18, 0.52)],
    "he":         [(0.32, 0.58)],
    "vav":        [(0.10, 0.36)],
    "zayin":      [(0.06, 0.24), (0.76, 0.94)],
    "xet":        [(0.03, 0.12), (0.27, 0.33), (0.64, 0.70), (0.89, 0.97)],
    "tet":        [(0.03, 0.12)],
    "yod":        [(0.24, 0.46)],
    "finalkaf":   [(0.18, 0.58)],
    "finalmem":   [(0.34, 0.64)],
    "nun":        [(0.05, 0.32)],
    "finalnun":   [(0.06, 0.24), (0.76, 0.94)],
    "samekh":     [(0.38, 0.62)],
    "ayin":       [(0.03, 0.11), (0.30, 0.36)],
    "pe":         [(0.46, 0.64)],
    "finalpe":    [(0.48, 0.66)],
    "tsadi":      [(0.03, 0.13)],
    "finaltsadi": [(0.03, 0.13)],
    "qof":        [(0.30, 0.62)],
    "resh":       [(0.18, 0.58)],
    "tav":        [(0.38, 0.62)],
}

BOT_L3_WINDOWS: dict[str, list[tuple[float, float]]] = {
    "bet":        [(0.22, 0.62)],
    "gimel":      [(0.05, 0.36)],
    "tet":        [(0.36, 0.56)],
    "mem":        [(0.42, 0.66)],
    "finalmem":   [(0.34, 0.64)],
    "nun":        [(0.05, 0.42)],
    "pe":         [(0.18, 0.56)],
    "tsadi":      [(0.05, 0.44)],
}


def build_kaf_perfect_ops() -> tuple[list[tuple], tuple[float, float, float, float]]:
    """Construct Sefardi kaf (כ) with exact horizontal lines on 1115 / 755 / 360 / 0,
    canonical +82u top-left concave serif, crisp aligned left ends, and G1/G2-smooth
    monotonically convex outer shoulder/heel and inner U-bend fitted to Mishnas Sofrim."""
    ops = [
        ("moveTo", ((0.0, 1197.0),)),
        ("curveTo", ((14.72, 1149.99), (45.39, 1122.65), (92.0, 1115.0))),
        ("lineTo", ((545.0, 1115.0),)),
        ("curveTo", ((785.0, 1115.0), (925.0, 935.0), (925.0, 565.0))),
        ("curveTo", ((925.0, 215.0), (775.0, 0.0), (525.0, 0.0))),
        ("lineTo", ((0.0, 0.0),)),
        ("lineTo", ((0.0, 360.0),)),
        ("lineTo", ((590.0, 360.0),)),
        ("curveTo", ((700.0, 360.0), (765.0, 425.0), (765.0, 557.5))),
        ("curveTo", ((765.0, 690.0), (700.0, 755.0), (590.0, 755.0))),
        ("lineTo", ((0.0, 755.0),)),
        ("lineTo", ((0.0, 1197.0),)),
        ("closePath", ()),
    ]
    return ops, (0.0, 0.0, 925.0, 1197.0)


def _render_kaf_perfect_mask() -> np.ndarray:
    ops, _ = build_kaf_perfect_ops()
    W_m, H_m = 900, 960
    sc = 0.68
    ox, oy = 140.0, 880.0
    pts = []
    cur = (0.0, 0.0)
    for op, args in ops:
        if op == "moveTo":
            cur = args[0]
            pts.append([ox + cur[0] * sc, oy - cur[1] * sc])
        elif op == "lineTo":
            cur = args[0]
            pts.append([ox + cur[0] * sc, oy - cur[1] * sc])
        elif op == "curveTo":
            p0 = cur
            p1, p2, p3 = args
            for t in np.linspace(0.04, 1.0, 25):
                m = 1.0 - t
                x = m**3 * p0[0] + 3*m*m*t * p1[0] + 3*m*t*t * p2[0] + t**3 * p3[0]
                y = m**3 * p0[1] + 3*m*m*t * p1[1] + 3*m*t*t * p2[1] + t**3 * p3[1]
                pts.append([ox + x * sc, oy - y * sc])
            cur = p3
    mask = np.zeros((H_m, W_m), dtype=np.uint8)
    poly_s4 = np.round(np.array(pts, dtype=np.float64) * 16.0).astype(np.int32)
    cv2.fillPoly(mask, [poly_s4], 255, shift=4)
    return mask


def _measure_inner_bar_knots(mask: np.ndarray, gname: str, ry0_m: float, ry1_m: float) -> tuple[float | None, float | None]:
    """Measure raw y-up coordinates of top-bar underside (for L2=755) and bottom-bar upper face (for L3=360)."""
    H2, W2 = mask.shape
    ys, xs = np.where(mask > 0)
    if len(ys) == 0:
        return None, None
    bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
    bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)

    ry_t2 = None
    if gname in TOP_L2_WINDOWS:
        y_start = max(0, int(round(H2 - ry1_m)) + 4)
        max_frac = 0.36 if gname == "ayin" else 0.52
        y_lim = min(H2, int(round(H2 - ry1_m)) + int(bh * max_frac))
        vals = []
        for f0, f1 in TOP_L2_WINDOWS[gname]:
            for x in range(bx0 + int(bw * f0), min(W2, bx0 + int(bw * f1) + 1)):
                col = mask[y_start:y_lim, x]
                idx = np.where(col > 0)[0]
                if len(idx):
                    s = idx[0]
                    e = s
                    while e + 1 < len(col) and col[e + 1] > 0:
                        e += 1
                    if e + 4 < len(col) and np.sum(col[e + 1 : min(len(col), e + 8)]) == 0:
                        vals.append(y_start + e)
        if vals:
            ry_t2 = float(H2) - float(np.median(vals))

    ry_b1 = None
    if gname in BOT_L3_WINDOWS:
        y_end = min(H2, int(round(H2 - ry0_m)) - 3)
        y_lim0 = max(0, int(round(H2 - ry0_m)) - int(bh * 0.52))
        vals = []
        for f0, f1 in BOT_L3_WINDOWS[gname]:
            for x in range(bx0 + int(bw * f0), min(W2, bx0 + int(bw * f1) + 1)):
                col = mask[y_lim0:y_end, x]
                idx = np.where(col > 0)[0]
                if len(idx):
                    e = idx[-1]
                    s = e
                    while s - 1 >= 0 and col[s - 1] > 0:
                        s -= 1
                    if s >= 4 and np.sum(col[max(0, s - 7) : s]) == 0:
                        vals.append(y_lim0 + s)
        if vals:
            ry_b1 = float(H2) - float(np.median(vals))

    return ry_b1, ry_t2


def mask_to_normalized_ops(gname: str, mask: np.ndarray) -> tuple[list[tuple], tuple[float, float, float, float]]:
    if gname == "kaf":
        return build_kaf_perfect_ops()

    cnts, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return [], (0, 0, 500, BODY_H)

    H2, W2 = mask.shape
    rx0, ry0_m, rx1, ry1_m = _measure_mask_main_anchors(mask, gname)

    if gname == "lamed":
        ys, xs = np.where(mask > 0)
        bx0, by0, bx1, by1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        bw, bh = max(1, bx1 - bx0), max(1, by1 - by0)
        # Measure horizontal middle crossbar top & bottom edges in y-img
        bar_tops, bar_bots = [], []
        for x in range(bx0 + int(bw * 0.36), bx0 + int(bw * 0.68)):
            ym = np.where(mask[by0 + int(bh * 0.35):by0 + int(bh * 0.78), x] > 0)[0]
            if len(ym):
                bar_tops.append(by0 + int(bh * 0.35) + int(ym[0]))
                bar_bots.append(by0 + int(bh * 0.35) + int(ym[-1]))
        bar_top_img = float(np.median(bar_tops)) if bar_tops else (by0 + bh * 0.50)
        bar_bot_img = float(np.median(bar_bots)) if bar_bots else (bar_top_img + bh * 0.17)
        bar_top_up = H2 - bar_top_img
        bar_bot_up = H2 - bar_bot_img
        bot_up = H2 - float(by1)
        head_top_up = H2 - float(by0)
        scale_y = (LINE_2_TOP_INNER - (-18.0)) / max(1.0, bar_bot_up - bot_up)
    else:
        target_y0, target_y1 = CALIBRATION[gname]
        raw_main_h = max(1.0, ry1_m - ry0_m)
        scale_y = (target_y1 - target_y0) / raw_main_h

    raw_w = max(1.0, rx1 - rx0)
    target_w = float(TARGET_WIDTHS[gname])
    scale_x_raw = target_w / raw_w
    scale_x = max(0.76 * scale_y, min(1.32 * scale_y, scale_x_raw))

    raw_ops = []
    sm_sig = 0.8 if gname == "xet" else 1.8
    m_err = 1.4 if gname == "xet" else 2.2
    for idx, hinfo in enumerate(hier[0]):
        parent = hinfo[3]
        if cv2.contourArea(cnts[idx]) < 80:
            continue
        pts_xy = cnts[idx][:, 0, :].astype(np.float64)
        pts_y_up = np.column_stack([pts_xy[:, 0], H2 - pts_xy[:, 1]])
        sa = 0.5 * np.sum(pts_y_up[:, 0] * np.roll(pts_y_up[:, 1], -1) - np.roll(pts_y_up[:, 0], -1) * pts_y_up[:, 1])
        is_hole = (parent != -1)
        want_cw = not is_hole
        if (sa > 0 and want_cw) or (sa < 0 and not want_cw):
            pts_y_up = pts_y_up[::-1]

        if gname == "lamed":
            pts_mapped = _lamed_piecewise_y(pts_y_up, bar_top_up, bar_bot_up, bot_up, head_top_up)
            pts_mapped[:, 0] = (pts_mapped[:, 0] - rx0) * scale_x
            raw_ops.extend(contour_to_cubics(pts_mapped, is_hole=is_hole, smooth_sigma=sm_sig, max_err=m_err))
        else:
            raw_ops.extend(contour_to_cubics(pts_y_up, is_hole=is_hole, smooth_sigma=sm_sig, max_err=m_err))

    rpen = RecordingPen()
    rpen.value = raw_ops
    if gname == "lamed":
        b2 = BoundsPen(None)
        rpen.replay(b2)
        return rpen.value, b2.bounds

    target_y0, target_y1 = CALIBRATION[gname]
    dx_shift = -rx0 * scale_x
    ry_b1, ry_t2 = _measure_inner_bar_knots(mask, gname, ry0_m, ry1_m)
    min_y_up = float(H2 - np.max(np.where(mask > 0)[0]))
    bot_inner_target = 195.0 if gname == "pe" else (210.0 if gname == "tsadi" else float(LINE_3_BOT_INNER))

    knots: list[tuple[float, float]] = [(ry0_m, float(target_y0))]
    if ry_b1 is not None and (ry0_m + 14.0) < ry_b1 < (ry1_m - 24.0):
        knots.append((ry_b1, bot_inner_target))
    if ry_t2 is not None and (knots[-1][0] + 14.0) < ry_t2 < (ry1_m - 14.0):
        knots.append((ry_t2, float(LINE_2_TOP_INNER)))
    knots.append((ry1_m, float(target_y1)))

    if gname == "gimel":
        sc_below = 90.0 / max(1.0, knots[0][0] - min_y_up)
    elif gname == "samekh":
        sc_below = 58.0 / max(1.0, knots[0][0] - min_y_up)
    else:
        sc_below = scale_y

    def map_pt(pt: tuple[float, float]) -> tuple[float, float]:
        nx = pt[0] * scale_x + dx_shift
        yv = pt[1]
        if yv <= knots[0][0]:
            ny = knots[0][1] + (yv - knots[0][0]) * sc_below
        elif yv >= knots[-1][0]:
            ny = knots[-1][1] + (yv - knots[-1][0]) * scale_y
        else:
            ny = knots[-1][1]
            for ik in range(len(knots) - 1):
                s0, d0 = knots[ik]
                s1, d1 = knots[ik + 1]
                if yv <= s1:
                    ny = d0 + (yv - s0) * ((d1 - d0) / max(1e-4, s1 - s0))
                    break
        return (nx, ny)

    mapped_ops = []
    for op, args in raw_ops:
        if args:
            mapped_ops.append((op, tuple(map_pt(p) for p in args)))
        else:
            mapped_ops.append((op, ()))

    scaled_pen = RecordingPen()
    scaled_pen.value = mapped_ops
    b2 = BoundsPen(None)
    scaled_pen.replay(b2)
    return scaled_pen.value, b2.bounds


def add_vector_tagin(gname: str, body_ops: list[tuple], bounds: tuple[float, float, float, float]) -> list[tuple]:
    if gname not in TAGIN_3 and gname not in TAGIN_1:
        return body_ops

    x0, y0, x1, y1 = bounds
    step = 4
    w_px = max(20, int((x1 - x0) / step) + 10)
    h_px = max(20, int((y1 - y0) / step) + 10)
    img = Image.new("L", (w_px, h_px), 0)
    poly_pts = []
    cur = []
    for op, args in body_ops:
        if op == "moveTo":
            cur = [args[0]]
        elif op == "lineTo":
            cur.append(args[0])
        elif op == "curveTo":
            p0 = cur[-1]
            p1, p2, p3 = args
            for s in (0.25, 0.5, 0.75, 1.0):
                m = 1.0 - s
                cur.append((
                    m**3 * p0[0] + 3*m*m*s * p1[0] + 3*m*s*s * p2[0] + s**3 * p3[0],
                    m**3 * p0[1] + 3*m*m*s * p1[1] + 3*m*s*s * p2[1] + s**3 * p3[1],
                ))
        elif op == "closePath":
            if len(cur) >= 3:
                poly_pts.append([((p[0] - x0) / step + 4, (y1 - p[1]) / step + 4) for p in cur])
            cur = []
    dr = ImageDraw.Draw(img)
    for poly in poly_pts:
        dr.polygon(poly, fill=255)
    arr = np.array(img)

    def find_runs_at_y(y_val: float, x_lim: tuple[float, float] | None = None):
        r_idx = int(np.clip((y1 - y_val) / step + 4, 0, h_px - 1))
        xs_ink = np.where(arr[r_idx] > 128)[0]
        if x_lim is not None:
            lx0, lx1 = (x_lim[0] - x0) / step + 4, (x_lim[1] - x0) / step + 4
            xs_ink = xs_ink[(xs_ink >= lx0) & (xs_ink <= lx1)]
        if len(xs_ink) == 0:
            return []
        runs, s, p = [], xs_ink[0], xs_ink[0]
        for xv in xs_ink[1:]:
            if xv - p > 3:
                runs.append((s, p))
                s = xv
            p = xv
        runs.append((s, p))
        return [(x0 + (a - 4) * step, x0 + (b - 4) * step) for a, b in runs]

    multi_head = gname in ("shin", "tet", "ayin", "tsadi", "finaltsadi", "xet")
    if multi_head:
        sep_y = BODY_H * (0.76 if gname != "tet" else 0.72)
        sep_runs = find_runs_at_y(sep_y)
        if not sep_runs:
            sep_runs = find_runs_at_y(BODY_H * 0.84)
        if gname == "xet" and sep_runs:
            l_win = (sep_runs[0][0] + 10.0, max(sep_runs[0][0] + 50.0, sep_runs[0][1] - 40.0))
            head_top_y = float(LINE_1_TOP_OUTER)
            for y_probe in range(int(LINE_1_TOP_OUTER + 80), int(BODY_H * 0.65), -step):
                r_list = find_runs_at_y(y_probe, l_win)
                if r_list and (r_list[0][1] - r_list[0][0]) >= 50.0:
                    head_top_y = float(y_probe)
                    break
            rx0, rx1 = sep_runs[0]
            base_y = head_top_y - 6.0
        elif gname == "shin" and sep_runs:
            # Left flat square head strictly at sep_runs[0]
            rx0, rx1 = sep_runs[0]
            head_top_y = float(LINE_1_TOP_OUTER)
            l_win = (rx0 + 10.0, rx1 - 10.0)
            for y_probe in range(int(LINE_1_TOP_OUTER + 60), int(BODY_H * 0.65), -step):
                r_list = find_runs_at_y(y_probe, l_win)
                if r_list and (r_list[0][1] - r_list[0][0]) >= (rx1 - rx0) * 0.60:
                    head_top_y = float(y_probe)
                    break
            base_y = head_top_y - 6.0
        else:
            l_win = (sep_runs[0][0] - 110.0, sep_runs[0][1] + 110.0) if sep_runs else (x0, x0 + (x1 - x0) * 0.45)
            head_top_y = None
            head_runs = []
            for y_probe in range(int(y1), int(BODY_H * 0.55), -step):
                r_list = find_runs_at_y(y_probe, l_win)
                if r_list:
                    if head_top_y is None:
                        head_top_y = float(y_probe)
                    if y_probe <= head_top_y - 24:
                        head_runs = r_list
                        break
            if head_top_y is None:
                head_top_y = float(BODY_H)
            rx0, rx1 = head_runs[0] if head_runs else (l_win[0] + 60, l_win[1] - 60)
            base_y = head_top_y - 6.0
    else:
        # Probe at roof body height (~LINE_1 - 55), NOT in the protruding top-left serif peak!
        base_y = float(LINE_1_TOP_OUTER - 5)
        best_runs = find_runs_at_y(float(LINE_1_TOP_OUTER - 55))
        if not best_runs:
            for y_probe in range(int(LINE_1_TOP_OUTER - 15), int(BODY_H * 0.72), -step):
                r_list = find_runs_at_y(y_probe)
                if r_list:
                    best_runs = r_list
                    break
        if gname == "yod":
            best_w = 0
            for y_probe in range(int(y1 - 40), int(y0 + 80), -step):
                r_list = find_runs_at_y(y_probe)
                if r_list and (r_list[0][1] - r_list[0][0]) > best_w:
                    best_w = r_list[0][1] - r_list[0][0]
                    best_runs = r_list
        if best_runs:
            rx0, rx1 = best_runs[0]
        else:
            rx0, rx1 = x0, x0 + (x1 - x0) * 0.45

    tag_ops: list[tuple] = []
    # 10pt-ready sturdy stalk (~50u average width -> ~0.244pt at 10pt print)
    wb = 26.5  # 53u wide at base
    wt = 22.0  # 44u wide below head

    def draw_one_tag(cx_base: float, by_start: float, height: float, tilt_deg: float, scale_hd: float = 1.0):
        ang = math.radians(tilt_deg)
        dx = math.sin(ang) * height
        dy = math.cos(ang) * height
        nx, ny = math.cos(ang), -math.sin(ang)
        ux, uy = math.sin(ang), math.cos(ang)
        bx0, by0 = cx_base, by_start - 26.0
        tx0, ty0 = cx_base + dx, by_start + dy
        p_bl = (bx0 - nx * wb, by0 - ny * wb)
        p_tl = (tx0 - nx * wt, ty0 - ny * wt)
        p_tr = (tx0 + nx * wt, ty0 + ny * wt)
        p_br = (bx0 + nx * wb, by0 + ny * wb)
        tag_ops.extend([
            ("moveTo", (p_bl,)),
            ("lineTo", (p_tl,)),
            ("lineTo", (p_tr,)),
            ("lineTo", (p_br,)),
            ("closePath", ()),
        ])
        # Calligraphic "Zayin / Drop" head (כעין זי״ן קטנים)
        s = scale_hd

        def pt_local(lx: float, ly: float) -> tuple[float, float]:
            return (tx0 + nx * lx + ux * ly, ty0 + ny * lx + uy * ly)

        p_top_l = pt_local(-62.0 * s, +44.0 * s)
        p_top_r = pt_local(+38.0 * s, +30.0 * s)
        p_bot_r = pt_local(+42.0 * s, -26.0 * s)
        p_join_r = pt_local(+wt, -52.0 * s)
        p_join_l = pt_local(-wt, -32.0 * s)
        p_beak_l = pt_local(-58.0 * s, -6.0 * s)
        tag_ops.extend([
            ("moveTo", (p_top_l,)),
            ("lineTo", (p_top_r,)),
            ("curveTo", (pt_local(+46.0 * s, +8.0 * s), pt_local(+46.0 * s, -12.0 * s), p_bot_r)),
            ("curveTo", (pt_local(+34.0 * s, -38.0 * s), pt_local(+wt + 4.0, -44.0 * s), p_join_r)),
            ("lineTo", (p_join_l,)),
            ("curveTo", (pt_local(-wt - 8.0, -18.0 * s), pt_local(-44.0 * s, -10.0 * s), p_beak_l)),
            ("lineTo", (p_top_l,)),
            ("closePath", ()),
        ])

    rw = max(60.0, rx1 - rx0)
    cx = (rx0 + rx1) / 2.0

    if gname in TAGIN_3:
        spread = min(140.0, max(68.0, rw * 0.38))
        draw_one_tag(cx - spread, base_y, 240.0, -10.5, 0.96)
        draw_one_tag(cx,          base_y, 322.0,   0.0, 1.04)
        draw_one_tag(cx + spread, base_y, 240.0, +10.5, 0.96)
    elif gname in TAGIN_1:
        tag_h = 255.0
        if gname == "xet":
            tx = cx
            tag_h = 295.0
        elif gname == "yod":
            base_y = float(LINE_1_TOP_OUTER - 5)
            tx = rx0 + rw * 0.56
            tag_h = 265.0
        elif gname == "qof":
            tx = rx0 + min(rw * 0.25, 165.0)
        else:
            # bet, dalet, he: place single tag cleanly JUST RIGHT of the restored top-left serif!
            tx = rx0 + min(rw * 0.23, 165.0)
        draw_one_tag(tx, base_y, tag_h, 0.0, 1.04)

    return body_ops + tag_ops


def build_outlines_ttf(glyph_data: dict[str, tuple[list[tuple], tuple[float, float, float, float]]]) -> None:
    glyph_order = [".notdef", "space"] + [g for g in glyph_data]
    fb = FontBuilder(UPEM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)

    cmap = {0x20: "space"}
    glyf_dict = {}
    metrics = {".notdef": (600, 0), "space": (520, 0)}

    p_nd = TTGlyphPen(None)
    p_nd.moveTo((100, 0)); p_nd.lineTo((100, 1000)); p_nd.lineTo((500, 1000)); p_nd.lineTo((500, 0)); p_nd.closePath()
    glyf_dict[".notdef"] = p_nd.glyph()
    glyf_dict["space"] = TTGlyphPen(None).glyph()

    LSB = 75
    RSB = 75
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    for gname, (ops, _) in glyph_data.items():
        cp = manifest[gname]["codepoint"]
        cmap[cp] = gname
        rp = RecordingPen()
        rp.value = ops
        bp = BoundsPen(None)
        rp.replay(bp)
        x0, y0, x1, y1 = bp.bounds
        if gname == "lamed":
            # Align lamed's main horizontal crossbar/stem body (y <= 1250) to normal LSB=75
            # rather than its protruding upper ascender head, eliminating excess left gap in ירושלם / אלהים.
            body_xs = []
            for _, args in ops:
                for pt in args:
                    if pt[1] <= 1250.0:
                        body_xs.append(pt[0])
            anchor_x0 = min(body_xs) if body_xs else x0
        else:
            anchor_x0 = x0
        shift_x = LSB - anchor_x0

        tt_pen = TTGlyphPen(None)
        q_pen = Cu2QuPen(tt_pen, max_err=1.2, reverse_direction=False)
        t_pen = TransformPen(q_pen, (1, 0, 0, 1, shift_x, 0))
        rp.replay(t_pen)
        g = tt_pen.glyph()
        if g.numberOfContours > 0:
            for idx in range(len(g.coordinates)):
                cx, cy = g.coordinates[idx]
                g.coordinates[idx] = (int(round(cx)), int(round(cy)))
        glyf_dict[gname] = g
        width_shifted = int(round(x1 - anchor_x0))
        metrics[gname] = (LSB + width_shifted + RSB, int(round(x0 + shift_x)))

    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyf_dict)
    for gname in glyph_data:
        g = fb.font["glyf"][gname]
        g.recalcBounds(fb.font["glyf"])
        metrics[gname] = (metrics[gname][0], g.xMin)

    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=1850, descent=-700)
    fb.setupNameTable({"familyName": "SefardiStamHayomOutlinesV3", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=1850, sTypoDescender=-700, usWinAscent=2050, usWinDescent=700)
    fb.setupPost()
    fb.save(str(OUTLINES_TTF))
    print("Saved v3 outlines TTF:", OUTLINES_TTF)


def render_trace_check(manifest: dict, cleaned_masks: dict[str, np.ndarray]) -> None:
    pil_font = ImageFont.truetype(str(OUTLINES_TTF), 120)
    lbl_font = ImageFont.load_default()
    small_font = ImageFont.load_default()
    try:
        lbl_font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 17)
        small_font = ImageFont.truetype(r"C:\Windows\Fonts\segoeui.ttf", 13)
    except Exception:
        pass

    cols = 4
    rows_n = math.ceil(len(manifest) / cols)
    cell_w, cell_h = 460, 200
    sheet = Image.new("RGB", (cols * cell_w + 20, rows_n * cell_h + 68), (250, 248, 242))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (20, 12),
        "v3 Trace Check (4 Horizontal Guide Lines: 1115 / 755 / 360 / 0  +  5-Column Vertical Width Grid: 5/5=925u, 2/5=370u)",
        fill=(25, 25, 30),
        font=lbl_font,
    )
    draw.text(
        (20, 34),
        "Verify: L1..L2 (755..1115) & L3..L4 (0..360) bars exact | yod roof at L1 | unwarped kaf | gimel/shin/samekh dip < L4 | 5-div width grid",
        fill=(85, 78, 70),
        font=small_font,
    )

    for idx, (gname, info) in enumerate(manifest.items()):
        r, c = divmod(idx, cols)
        ox = 10 + c * cell_w
        oy = 58 + r * cell_h
        draw.rectangle([ox + 2, oy + 2, ox + cell_w - 4, oy + cell_h - 4], outline=(210, 205, 195), fill=(255, 255, 255), width=1)
        draw.text((ox + 10, oy + 6), f"{gname} ({info['rule']})", fill=(140, 30, 30), font=lbl_font)

        crop = Image.open(DESKEW_DIR / f"{gname}.png").convert("RGB")
        crop.thumbnail((135, 150), Image.Resampling.LANCZOS)
        sheet.paste(crop, (ox + 8 + (135 - crop.width) // 2, oy + 36 + (150 - crop.height) // 2))

        m = cleaned_masks[gname]
        ys, xs = np.where(m > 0)
        mcrop = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        m_pil = Image.fromarray(255 - mcrop).convert("RGB")
        m_pil.thumbnail((130, 145), Image.Resampling.LANCZOS)
        sheet.paste(m_pil, (ox + 158 + (130 - m_pil.width) // 2, oy + 38 + (145 - m_pil.height) // 2))

        px_l4 = oy + 152  # baseline y = 0
        px_l3 = int(round(px_l4 - LINE_3_BOT_INNER / UPEM * 120))
        px_l2 = int(round(px_l4 - LINE_2_TOP_INNER / UPEM * 120))
        px_l1 = int(round(px_l4 - LINE_1_TOP_OUTER / UPEM * 120))

        draw.line([ox + 305, px_l1, ox + 448, px_l1], fill=(55, 125, 225), width=1)    # L1 blue
        draw.line([ox + 305, px_l2, ox + 448, px_l2], fill=(95, 195, 220), width=1)    # L2 cyan
        draw.line([ox + 305, px_l3, ox + 448, px_l3], fill=(235, 195, 75), width=1)    # L3 gold
        draw.line([ox + 305, px_l4, ox + 448, px_l4], fill=(225, 120, 45), width=1)    # L4 orange

        ch = info["char"]
        bbox_t = draw.textbbox((0, 0), ch, font=pil_font, anchor="ls")
        tw = bbox_t[2] - bbox_t[0]
        gx = ox + 305 + (140 - tw) // 2 - bbox_t[0]
        rx_ink = gx + bbox_t[2]  # right edge of glyph ink (RTL origin)
        # Draw 5-division vertical grid leftward from glyph right edge (5/5 = STD_GRID_W = 925u)
        vx_top, vx_bot = px_l1 - 24, px_l4 + 12
        for k in range(6):
            vx = int(round(rx_ink - (k / 5.0) * STD_GRID_W / UPEM * 120))
            if k in (0, 5):
                col_v = (165, 160, 195)
            elif k == 2:
                col_v = (180, 130, 185)  # highlight 2/5 mark for narrow vav/zayin/yod/finalnun
            else:
                col_v = (225, 222, 215)
            draw.line([vx, vx_top, vx, vx_bot], fill=col_v, width=1)

        draw.text((gx, px_l4), ch, fill=(10, 10, 15), font=pil_font, anchor="ls")

    sheet.save(TRACE_CHECK_PNG)
    print("Saved v3 trace check:", TRACE_CHECK_PNG)


def main():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    cleaned_masks = {}
    glyph_data = {}

    for gname, info in manifest.items():
        crop_bgr = cv2.imread(str(DESKEW_DIR / f"{gname}.png"))
        mask = extract_clean_mask(crop_bgr, gname)
        cv2.imwrite(str(MASK_DIR / f"{gname}.png"), mask)
        cleaned_masks[gname] = mask

        body_ops, bounds = mask_to_normalized_ops(gname, mask)
        full_ops = add_vector_tagin(gname, body_ops, bounds)
        glyph_data[gname] = (full_ops, bounds)
        print(f"  {gname:10s}: body y=[{bounds[1]:5.0f},{bounds[3]:4.0f}] w={bounds[2]-bounds[0]:4.0f} (tgt={TARGET_WIDTHS[gname]:4d})")

    build_outlines_ttf(glyph_data)
    render_trace_check(manifest, cleaned_masks)


if __name__ == "__main__":
    main()
