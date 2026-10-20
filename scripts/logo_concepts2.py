"""타임줍 로고 시안 2차 (E~L, 8종).

사용: python scripts/logo_concepts2.py [저장할 폴더]
결과: <폴더>/타임줍_로고시안2.png (4x2), 각 시안 logo_<E~L>.png
"""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from logo_concepts import (  # noqa: E402
    BLACK, JALNAN, LABEL, LIME, PINK, S, USER_FONTS, WHITE, big_gradient, canvas, font, play, rounded_mask, sparkle,
)

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "data" / "logo"
OUT.mkdir(parents=True, exist_ok=True)
GMARKET = str(USER_FONTS / "GmarketSansTTFBold.ttf")
MONT = str(USER_FONTS / "Montserrat-Black.otf")


def bg(color_or_img):
    img = canvas()
    src = color_or_img if isinstance(color_or_img, Image.Image) else Image.new("RGBA", (S, S), color_or_img)
    img.paste(src, (0, 0), rounded_mask())
    return img


def text_mask(text, fnt, xy):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).text(xy, text, font=fnt, fill=255, anchor="mm")
    return m


def multi_gradient(stops, vertical=True):
    g = Image.new("RGBA", (1, 256) if vertical else (256, 1))
    px = g.load()
    for i in range(256):
        t = i / 255
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t <= t1:
                k = (t - t0) / (t1 - t0) if t1 > t0 else 0
                c = tuple(round(a + (b - a) * k) for a, b in zip(c0, c1))
                px[(0, i) if vertical else (i, 0)] = c
                break
    return g.resize((S, S), Image.BICUBIC)


def capsule(d, a, b, w, fill):
    d.line([a, b], fill=fill, width=w)
    for x, y in (a, b):
        d.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=fill)


# ---------- E. 픽셀아트 ----------
PIXELS = [
    "................",
    ".............P..",
    "............PWP.",
    ".....KKKKK...P..",
    "...KKLLLLLKK....",
    "..KLLLLKLLLLK...",
    "..KLLLLKLLLLK...",
    ".KLLLLLKLLLLLK..",
    ".KLLLLLKKKLLLK..",
    ".KLLLLLLLLLLLK..",
    "..KLLLLLLLLLK...",
    "..KLLLLLLLLLK...",
    "...KKLLLLLKK....",
    ".....KKKKK......",
    "................",
    "................",
]


def concept_e():
    colors = {".": (27, 27, 58, 255), "K": BLACK, "L": LIME, "P": PINK, "W": WHITE}
    small = Image.new("RGBA", (16, 16))
    for y, row in enumerate(PIXELS):
        for x, ch in enumerate(row):
            small.putpixel((x, y), colors[ch])
    return bg(small.resize((S, S), Image.NEAREST))


# ---------- F. 젤리 3D ----------
def concept_f():
    img = bg(big_gradient((185, 166, 255), (125, 211, 252)))
    m = text_mask("줍", font(JALNAN, 620), (512, 520))
    shadow = Image.new("RGBA", (S, S), (76, 29, 149, 0))
    shadow.putalpha(m.filter(ImageFilter.GaussianBlur(22)).point(lambda v: v * 0.7))
    img.alpha_composite(shadow, (18, 34))
    img.paste(multi_gradient([(0, (255, 140, 200, 255)), (1, (255, 92, 70, 255))]), (0, 0), m)
    # 위쪽 광택
    gloss = Image.new("L", (S, S), 0)
    ImageDraw.Draw(gloss).ellipse([170, 150, 860, 470], fill=150)
    gloss = Image.composite(gloss.filter(ImageFilter.GaussianBlur(30)), Image.new("L", (S, S), 0), m.filter(ImageFilter.MinFilter(25)))
    img.alpha_composite(Image.merge("RGBA", (*[Image.new("L", (S, S), 255)] * 3, gloss)))
    d = ImageDraw.Draw(img)
    sparkle(d, 830, 190, 70, 16, WHITE)
    d.ellipse([170, 790, 210, 830], fill=WHITE)
    return img


# ---------- G. 집게손 ----------
def concept_g():
    img = bg(LIME)
    d = ImageDraw.Draw(img)
    skin = (255, 214, 186, 255)
    cx, cy, r = 600, 512, 95
    for w, c in ((170, BLACK), (122, skin)):
        capsule(d, (40, 330), (cx - 30, cy - r - 52), w, c)   # 검지
        capsule(d, (40, 700), (cx - 30, cy + r + 52), w, c)   # 엄지
    hand = [-200, 260, 170, 770]
    d.rounded_rectangle(hand, radius=180, fill=BLACK)
    d.rounded_rectangle([hand[0], hand[1] + 24, hand[2] - 24, hand[3] - 24], radius=160, fill=skin)
    for y in (cy - r - 52, cy + r + 52):  # 손톱
        d.ellipse([cx - 30 - 34, y - 34, cx - 30 + 34, y + 34], fill=(255, 241, 232, 255))
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK, outline=BLACK, width=26)
    play(d, cx + 8, cy, r * 0.75, WHITE)
    for a in (-35, 0, 35):  # 반짝 선
        x0, y0 = cx + math.cos(math.radians(a)) * 165, cy + math.sin(math.radians(a)) * 165
        x1, y1 = cx + math.cos(math.radians(a)) * 245, cy + math.sin(math.radians(a)) * 245
        capsule(d, (x0, y0), (x1, y1), 28, BLACK)
    sparkle(d, 850, 200, 60, 14, BLACK)
    return img


# ---------- H. Y2K 크롬 ----------
def concept_h():
    img = bg(big_gradient((30, 58, 138), (2, 6, 23)))
    m = text_mask("줍", font(JALNAN, 640), (512, 520))
    outline = m.filter(ImageFilter.MaxFilter(31))
    img.paste(Image.new("RGBA", (S, S), (147, 197, 253, 255)), (0, 0), outline.filter(ImageFilter.GaussianBlur(14)))
    img.paste(Image.new("RGBA", (S, S), (15, 23, 42, 255)), (0, 0), m.filter(ImageFilter.MaxFilter(13)))
    chrome = multi_gradient([(0, (255, 255, 255, 255)), (0.35, (148, 163, 184, 255)), (0.5, (255, 255, 255, 255)),
                             (0.62, (71, 85, 105, 255)), (1, (226, 232, 240, 255))])
    img.paste(chrome, (0, 0), m)
    d = ImageDraw.Draw(img)
    for x, y, b in ((820, 180, 80), (200, 820, 56), (860, 760, 34), (190, 230, 30)):
        sparkle(d, x, y, b, b * 0.2, WHITE)
    return img


# ---------- I. 스탬프 ----------
def concept_i():
    red = (229, 56, 59, 255)
    img = bg((255, 244, 224, 255))
    layer = canvas()
    d = ImageDraw.Draw(layer)
    d.ellipse([110, 110, 914, 914], outline=red, width=34)
    d.ellipse([200, 200, 824, 824], outline=red, width=14)
    d.text((512, 525), "줍", font=font(JALNAN, 400), fill=red, anchor="mm")
    ring = "TIME · JUP · TIME · JUP · "
    f = font(MONT, 66)
    for i, ch in enumerate(ring):
        ang = -90 + i * 360 / len(ring)
        ch_img = Image.new("RGBA", (90, 90), (0, 0, 0, 0))
        ImageDraw.Draw(ch_img).text((45, 45), ch, font=f, fill=red, anchor="mm")
        ch_img = ch_img.rotate(-ang - 90, resample=Image.BICUBIC)
        x = 512 + math.cos(math.radians(ang)) * 357 - 45
        y = 512 + math.sin(math.radians(ang)) * 357 - 45
        layer.alpha_composite(ch_img, (round(x), round(y)))
    img.alpha_composite(layer.rotate(-14, resample=Image.BICUBIC))
    return img


# ---------- J. 형광펜 워드마크 ----------
def concept_j():
    img = bg(WHITE)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([18, 18, S - 19, S - 19], radius=215, outline=BLACK, width=26)
    hl = canvas()
    ImageDraw.Draw(hl).polygon([(615, 495), (905, 465), (918, 585), (605, 612)], fill=(214, 255, 58, 230))
    img.alpha_composite(hl)
    d.text((512, 470), "타임줍", font=font(GMARKET, 270), fill=BLACK, anchor="mm")
    d.text((512, 770), "재밌는 시간만 줍줍", font=font(GMARKET, 74), fill=(90, 90, 100, 255), anchor="mm")
    sparkle(d, 870, 270, 54, 12, PINK)
    return img


# ---------- K. 마스코트 줍이 ----------
def concept_k():
    img = bg((125, 211, 252, 255))
    d = ImageDraw.Draw(img)
    body = (255, 133, 179, 255)
    d.ellipse([180, 330, 844, 930], fill=BLACK)
    d.ellipse([200, 310, 824, 900], fill=body, outline=BLACK, width=28)
    for x in (400, 624):  # 눈
        d.ellipse([x - 42, 520, x + 42, 640], fill=BLACK)
        d.ellipse([x - 14, 540, x + 12, 572], fill=WHITE)
    for x in (300, 724):  # 볼터치
        d.ellipse([x - 55, 650, x + 55, 700], fill=(255, 90, 140, 255))
    d.arc([462, 640, 512, 700], 0, 180, fill=BLACK, width=16)  # w 입
    d.arc([512, 640, 562, 700], 0, 180, fill=BLACK, width=16)
    capsule(d, (650, 380), (760, 250), 70, BLACK)  # 팔 들고
    capsule(d, (650, 380), (760, 250), 40, body)
    d.ellipse([705, 70, 935, 300], fill=LIME, outline=BLACK, width=24)  # 주운 별
    sparkle(d, 820, 185, 80, 20, BLACK)
    return img


# ---------- L. 브루탈 타이포 ----------
def concept_l():
    img = bg(BLACK)
    d = ImageDraw.Draw(img)
    # TIME (위)
    f_time = font(MONT, 210)
    l, t, r, b = d.textbbox((0, 0), "TIME", font=f_time)
    time_top = 105
    d.text((512 - (l + r) / 2, time_top - t), "TIME", font=f_time, fill=WHITE)
    time_bottom = time_top + (b - t)
    # 핑크 줄: TIME 바로 아래
    line_top = time_bottom + 34
    d.rectangle([90, line_top, 934, line_top + 22], fill=PINK)
    # 줍: 줄과 겹치지 않게, 실제 글자 모양 높이로 크기를 맞춘다
    top, bottom = line_top + 22 + 46, 915
    f_jup = font(JALNAN, 100)
    l, t, r, b = d.textbbox((0, 0), "줍", font=f_jup)
    size = round(100 * (bottom - top) / (b - t))
    f_jup = font(JALNAN, size)
    l, t, r, b = d.textbbox((0, 0), "줍", font=f_jup)
    jx = 455 - (l + r) / 2
    d.text((jx, top - t), "줍", font=f_jup, fill=LIME)
    # 재생 버튼: 줍 오른쪽, 세로 가운데
    cy = (top + bottom) / 2
    px = jx + r + 50
    d.polygon([(px, cy - 120), (px, cy + 120), (px + 160, cy)], fill=PINK)
    return img


def concept_zoop(stacked: bool):
    """L(브루탈 타이포)의 '줍'을 영어 ZOOP으로. stacked면 ZO / OP 두 줄."""
    img = bg(BLACK)
    d = ImageDraw.Draw(img)
    f_time = font(MONT, 200 if stacked else 230)
    l, t, r, b = d.textbbox((0, 0), "TIME", font=f_time)
    time_top = 95 if stacked else 150
    d.text((512 - (l + r) / 2, time_top - t), "TIME", font=f_time, fill=WHITE)
    line_top = time_top + (b - t) + 30
    d.rectangle([90, line_top, 934, line_top + 22], fill=PINK)
    top, bottom = line_top + 22 + 42, 930 if stacked else 860
    lines = ["ZO", "OP"] if stacked else ["ZOOP"]
    gap = 26
    h_each = (bottom - top - gap * (len(lines) - 1)) / len(lines)
    width_max = 700 if stacked else 820
    probe = font(MONT, 100)
    pl, pt, pr, pb = d.textbbox((0, 0), "ZOOP" if not stacked else "ZO", font=probe)
    size = round(min(100 * h_each / (pb - pt), 100 * width_max / (pr - pl)))
    f = font(MONT, size)
    y = top
    right_edge = 0
    for text in lines:
        l, t, r, b = d.textbbox((0, 0), text, font=f)
        x = (455 if stacked else 512) - (l + r) / 2
        d.text((x, y - t), text, font=f, fill=LIME)
        right_edge = max(right_edge, x + r)
        y += (b - t) + gap
    if stacked:  # 재생 버튼: 두 줄 오른쪽 가운데
        cy = (top + bottom) / 2
        px = right_edge + 40
        d.polygon([(px, cy - 110), (px, cy + 110), (px + 150, cy)], fill=PINK)
    else:  # 한 줄이면 아래 빈 곳에 큰 ◀ 되감기 → ⏸ 일시정지 → ▶ 재생 버튼 (사용자 요청 순서)
        zoop_bottom = y - gap
        h = min(170, 935 - (zoop_bottom + 60))
        cy = (zoop_bottom + 60 + 935) / 2
        bar_w, bar_gap, group_gap, tri_w = h * 0.3, h * 0.24, h * 0.5, h * 0.88
        total_w = tri_w + group_gap + bar_w * 2 + bar_gap + group_gap + tri_w
        x = 512 - total_w / 2
        d.polygon([(x + tri_w, cy - h / 2), (x + tri_w, cy + h / 2), (x, cy)], fill=PINK)  # 뒤집은 재생
        x += tri_w + group_gap
        for _ in range(2):  # 일시정지: 둥근 막대 두 개
            d.rounded_rectangle([x, cy - h / 2, x + bar_w, cy + h / 2], radius=bar_w * 0.28, fill=PINK)
            x += bar_w + bar_gap
        x += group_gap - bar_gap
        d.polygon([(x, cy - h / 2), (x, cy + h / 2), (x + tri_w, cy)], fill=PINK)  # 재생
    return img


def concept_zoop_line_below(seek: bool, fill=None, knob=None, gradient=False):
    """TIME / ZOOP / 분홍 줄 / ◀ ⏸ ▶. seek면 줄을 재생 막대처럼 (채운 부분 + 손잡이)."""
    img = bg(BLACK)
    d = ImageDraw.Draw(img)
    f_time = font(MONT, 200)
    probe = font(MONT, 100)
    pl, pt, pr, pb = d.textbbox((0, 0), "ZOOP", font=probe)
    f_zoop = font(MONT, round(100 * 820 / (pr - pl)))
    tl, tt, tr, tb = d.textbbox((0, 0), "TIME", font=f_time)
    zl, zt, zr, zb = d.textbbox((0, 0), "ZOOP", font=f_zoop)
    th, zh = tb - tt, zb - zt
    h_btn, line_h = 150, 22
    gaps = (36, 52, 60)  # TIME-ZOOP, ZOOP-줄, 줄-버튼
    block = th + gaps[0] + zh + gaps[1] + line_h + gaps[2] + h_btn
    top = (1024 - block) / 2
    d.text((512 - (tl + tr) / 2, top - tt), "TIME", font=f_time, fill=WHITE)
    zy = top + th + gaps[0]
    d.text((512 - (zl + zr) / 2, zy - zt), "ZOOP", font=f_zoop, fill=LIME)
    ly = zy + zh + gaps[1]
    if seek:  # 재생 막대: 회색 트랙 + 분홍 채움 + 손잡이
        d.rounded_rectangle([90, ly, 934, ly + line_h], radius=line_h / 2, fill=(70, 70, 82, 255))
        knob_x = 90 + (934 - 90) * 0.62
        if gradient:  # 핑크 → 라임
            g = Image.new("RGBA", (round(knob_x - 90), line_h))
            for gx in range(g.width):
                t = gx / max(g.width - 1, 1)
                c = tuple(round(a + (b - a) * t) for a, b in zip(PINK, LIME))
                ImageDraw.Draw(g).line([(gx, 0), (gx, line_h)], fill=c)
            m = Image.new("L", g.size, 0)
            ImageDraw.Draw(m).rounded_rectangle([0, 0, g.width - 1, line_h - 1], radius=line_h / 2, fill=255)
            img.paste(g, (90, round(ly)), m)
        else:
            d.rounded_rectangle([90, ly, knob_x, ly + line_h], radius=line_h / 2, fill=fill or PINK)
        r = 34
        d.ellipse([knob_x - r, ly + line_h / 2 - r, knob_x + r, ly + line_h / 2 + r], fill=knob or WHITE)
    else:
        d.rectangle([90, ly, 934, ly + line_h], fill=PINK)
    # ◀ ⏸ ▶
    h = h_btn
    cy = ly + line_h + gaps[2] + h / 2
    bar_w, bar_gap, group_gap, tri_w = h * 0.3, h * 0.24, h * 0.5, h * 0.88
    total_w = tri_w + group_gap + bar_w * 2 + bar_gap + group_gap + tri_w
    x = 512 - total_w / 2
    d.polygon([(x + tri_w, cy - h / 2), (x + tri_w, cy + h / 2), (x, cy)], fill=PINK)
    x += tri_w + group_gap
    for _ in range(2):
        d.rounded_rectangle([x, cy - h / 2, x + bar_w, cy + h / 2], radius=bar_w * 0.28, fill=PINK)
        x += bar_w + bar_gap
    x += group_gap - bar_gap
    d.polygon([(x, cy - h / 2), (x, cy + h / 2), (x + tri_w, cy)], fill=PINK)
    return img


def main():
    if len(sys.argv) > 2 and sys.argv[2] == "seekcolors":
        variants = (("SK1", "1. 라임", dict(fill=LIME, knob=WHITE)),
                    ("SK2", "2. 흰색", dict(fill=WHITE, knob=LIME)),
                    ("SK3", "3. 핑크→라임", dict(gradient=True, knob=WHITE)))
        tile = 400
        sheet = Image.new("RGB", (36 + 3 * (tile + 36), 36 + tile + 64 + 36), (245, 246, 250))
        d = ImageDraw.Draw(sheet)
        f = font(LABEL, 28)
        for i, (key, name, kw) in enumerate(variants):
            img = concept_zoop_line_below(True, **kw)
            img.resize((512, 512), Image.LANCZOS).save(OUT / f"logo_{key}.png")
            t = img.resize((tile, tile), Image.LANCZOS)
            x = 36 + i * (tile + 36)
            sheet.paste(t, (x, 36), t)
            d.text((x + tile / 2, 36 + tile + 34), name, font=f, fill=(30, 32, 40), anchor="mm")
        sheet.save(OUT / "타임줍_로고_막대색.png")
        print(OUT / "타임줍_로고_막대색.png")
        return
    if len(sys.argv) > 2 and sys.argv[2] == "linebelow":
        variants = (("LB_A", "A안. 줄을 ZOOP 아래로", False), ("LB_B", "B안. 재생 막대처럼", True))
        sheet = Image.new("RGB", (36 + 2 * (460 + 36), 36 + 460 + 64 + 36), (245, 246, 250))
        d = ImageDraw.Draw(sheet)
        f = font(LABEL, 28)
        for i, (key, name, seek) in enumerate(variants):
            img = concept_zoop_line_below(seek)
            img.resize((512, 512), Image.LANCZOS).save(OUT / f"logo_{key}.png")
            t = img.resize((460, 460), Image.LANCZOS)
            x = 36 + i * (460 + 36)
            sheet.paste(t, (x, 36), t)
            d.text((x + 230, 36 + 460 + 34), name, font=f, fill=(30, 32, 40), anchor="mm")
        sheet.save(OUT / "타임줍_로고_줄아래.png")
        print(OUT / "타임줍_로고_줄아래.png")
        return
    if len(sys.argv) > 2 and sys.argv[2] == "zoop":
        for key, stacked in (("ZOOP1", False), ("ZOOP2", True)):
            concept_zoop(stacked).resize((512, 512), Image.LANCZOS).save(OUT / f"logo_{key}.png")
        sheet = Image.new("RGB", (36 + 2 * (460 + 36), 36 + 460 + 64 + 36), (245, 246, 250))
        d = ImageDraw.Draw(sheet)
        f = font(LABEL, 28)
        for i, (key, name) in enumerate((("ZOOP1", "1안. ZOOP 한 줄"), ("ZOOP2", "2안. ZO / OP 두 줄"))):
            t = Image.open(OUT / f"logo_{key}.png").resize((460, 460), Image.LANCZOS)
            x = 36 + i * (460 + 36)
            sheet.paste(t, (x, 36), t)
            d.text((x + 230, 36 + 460 + 34), name, font=f, fill=(30, 32, 40), anchor="mm")
        sheet.save(OUT / "타임줍_로고_ZOOP.png")
        print(OUT / "타임줍_로고_ZOOP.png")
        return
    concepts = [("E", "픽셀아트", concept_e()), ("F", "젤리 3D", concept_f()), ("G", "집게손", concept_g()),
                ("H", "Y2K 크롬", concept_h()), ("I", "스탬프", concept_i()), ("J", "형광펜 워드마크", concept_j()),
                ("K", "마스코트 줍이", concept_k()), ("L", "브루탈 타이포", concept_l())]
    tile, pad, label_h, cols = 380, 36, 64, 4
    rows = math.ceil(len(concepts) / cols)
    sheet = Image.new("RGB", (pad + cols * (tile + pad), pad + rows * (tile + label_h + pad)), (245, 246, 250))
    d = ImageDraw.Draw(sheet)
    f = font(LABEL, 28)
    for i, (key, name, img) in enumerate(concepts):
        img.resize((512, 512), Image.LANCZOS).save(OUT / f"logo_{key}.png")
        x = pad + (i % cols) * (tile + pad)
        y = pad + (i // cols) * (tile + label_h + pad)
        t = img.resize((tile, tile), Image.LANCZOS)
        sheet.paste(t, (x, y), t)
        d.text((x + tile / 2, y + tile + 34), f"{key}. {name}", font=f, fill=(30, 32, 40), anchor="mm")
    path = OUT / "타임줍_로고시안2.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
