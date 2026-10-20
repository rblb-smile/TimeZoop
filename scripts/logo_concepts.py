"""타임줍 로고 시안 4종을 그려 한 장으로 모은다.

사용: python scripts/logo_concepts.py [저장할 폴더]
결과: <폴더>/타임줍_로고시안.png (2x2), 각 시안 logo_<A~D>.png
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "logo"
OUT.mkdir(parents=True, exist_ok=True)
S = 1024
USER_FONTS = Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
JALNAN = str(USER_FONTS / "Jalnan2TTF.ttf")
JUA = str(USER_FONTS / "BM-JUA.ttf")
LABEL = "C:/Windows/Fonts/malgunbd.ttf"

BLACK = (12, 12, 18, 255)
WHITE = (255, 255, 255, 255)
LIME = (214, 255, 58, 255)
PINK = (255, 46, 136, 255)


def canvas(color=(0, 0, 0, 0)):
    return Image.new("RGBA", (S, S), color)


def font(path, size):
    return ImageFont.truetype(path, size)


def gradient(size, c0, c1, diagonal=True):
    w, h = size
    g = Image.new("RGBA", (w, h))
    px = g.load()
    for y in range(h):
        for x in range(w):
            t = (x + y) / (w + h - 2) if diagonal else y / (h - 1)
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(c0, c1))
    return g


def big_gradient(c0, c1, diagonal=True):
    return gradient((128, 128), c0, c1, diagonal).resize((S, S), Image.BICUBIC)


def play(d, cx, cy, r, fill):
    d.polygon([(cx - r * 0.45, cy - r * 0.6), (cx - r * 0.45, cy + r * 0.6), (cx + r * 0.6, cy)], fill=fill)


def sparkle(d, cx, cy, big, small, fill):
    d.polygon([(cx, cy - big), (cx + small, cy - small), (cx + big, cy), (cx + small, cy + small),
               (cx, cy + big), (cx - small, cy + small), (cx - big, cy), (cx - small, cy - small)], fill=fill)


def rounded_mask(radius=230):
    m = Image.new("L", (S, S), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, S - 1, S - 1], radius=radius, fill=255)
    return m


# ---------- A. 네온 스티커 ----------
def concept_a():
    layer = canvas()
    d = ImageDraw.Draw(layer)
    box = [120, 120, 880, 880]
    d.rounded_rectangle([b + 46 for b in box], radius=190, fill=BLACK)  # 딱딱한 그림자
    d.rounded_rectangle(box, radius=190, fill=LIME, outline=BLACK, width=34)
    d.text((470, 545), "줍", font=font(JALNAN, 470), fill=BLACK, anchor="mm")
    # 재생 배지
    cx, cy, r = 790, 215, 150
    d.ellipse([cx - r + 22, cy - r + 22, cx + r + 22, cy + r + 22], fill=BLACK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK, outline=BLACK, width=30)
    play(d, cx + 10, cy, r * 0.75, WHITE)
    sparkle(d, 215, 820, 70, 16, BLACK)
    return layer.rotate(-8, resample=Image.BICUBIC, center=(512, 512))


# ---------- B. 다크 네온 ----------
def concept_b():
    img = canvas()
    img.paste(Image.new("RGBA", (S, S), (11, 11, 18, 255)), (0, 0), rounded_mask())
    text_mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(text_mask).text((512, 440), "줍", font=font(JALNAN, 600), fill=255, anchor="mm")
    glow = Image.new("RGBA", (S, S), (255, 46, 136, 0))
    glow.putalpha(text_mask.filter(ImageFilter.GaussianBlur(40)))
    img.alpha_composite(glow)
    img.alpha_composite(glow)
    fill = big_gradient((255, 61, 139), (255, 176, 32), diagonal=False)
    img.paste(fill, (0, 0), text_mask)
    # 재생 막대: 회색 트랙 + 빛나는 하이라이트 구간
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([150, 800, 874, 836], radius=18, fill=(42, 42, 58, 255))
    hl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(hl).rounded_rectangle([430, 790, 690, 846], radius=28, fill=LIME)
    img.alpha_composite(hl.filter(ImageFilter.GaussianBlur(24)))
    d.rounded_rectangle([430, 800, 690, 836], radius=18, fill=LIME)
    d.ellipse([660, 778, 740, 858], fill=WHITE)
    return img


# ---------- C. 타임라인 줍기 (글자 없음) ----------
def concept_c():
    img = canvas()
    img.paste(big_gradient((255, 61, 139), (124, 58, 237)), (0, 0), rounded_mask())
    d = ImageDraw.Draw(img)
    y = 700
    d.rounded_rectangle([140, y - 22, 884, y + 22], radius=22, fill=(255, 255, 255, 120))
    for x in (250, 774):
        d.ellipse([x - 34, y - 34, x + 34, y + 34], fill=WHITE)
    # 트랙에서 쏙 집어 올린 한 순간
    d.line([(512, y), (512, 470)], fill=WHITE, width=26)
    d.ellipse([512 - 40, y - 40, 512 + 40, y + 40], fill=(255, 255, 255, 140))
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([512 - 210, 330 - 210, 512 + 210, 330 + 210], fill=LIME)
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(50)))
    d.ellipse([512 - 165, 330 - 165, 512 + 165, 330 + 165], fill=LIME, outline=BLACK, width=26)
    play(d, 528, 330, 120, BLACK)
    sparkle(d, 760, 190, 80, 18, WHITE)
    sparkle(d, 270, 250, 46, 11, WHITE)
    return img


# ---------- D. 줍줍 말풍선 ----------
def concept_d():
    img = canvas()
    img.paste(Image.new("RGBA", (S, S), (255, 225, 77, 255)), (0, 0), rounded_mask())
    d = ImageDraw.Draw(img)
    bubble = [120, 210, 904, 720]
    d.rounded_rectangle([b + 30 for b in bubble], radius=170, fill=BLACK)
    d.polygon([(330, 740), (300, 900), (470, 750)], fill=BLACK)
    d.rounded_rectangle(bubble, radius=170, fill=WHITE, outline=BLACK, width=30)
    d.polygon([(320, 700), (290, 860), (450, 712)], fill=WHITE, outline=BLACK, width=0)
    d.line([(320, 712), (290, 860), (450, 718)], fill=BLACK, width=30, joint="curve")
    d.text((512, 470), "줍줍", font=font(JUA, 330), fill=BLACK, anchor="mm")
    cx, cy, r = 830, 230, 110
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=PINK, outline=BLACK, width=26)
    play(d, cx + 8, cy, r * 0.75, WHITE)
    return img


def main():
    concepts = [("A", "네온 스티커", concept_a()), ("B", "다크 네온", concept_b()),
                ("C", "타임라인 줍기", concept_c()), ("D", "줍줍 말풍선", concept_d())]
    tile, pad, label_h = 460, 40, 70
    sheet = Image.new("RGB", (pad + 2 * (tile + pad), pad + 2 * (tile + label_h + pad)), (245, 246, 250))
    d = ImageDraw.Draw(sheet)
    f = font(LABEL, 30)
    for i, (key, name, img) in enumerate(concepts):
        img.resize((512, 512), Image.LANCZOS).save(OUT / f"logo_{key}.png")
        x = pad + (i % 2) * (tile + pad)
        y = pad + (i // 2) * (tile + label_h + pad)
        sheet.paste(img.resize((tile, tile), Image.LANCZOS), (x, y), img.resize((tile, tile), Image.LANCZOS))
        d.text((x + tile / 2, y + tile + 36), f"{key}. {name}", font=f, fill=(30, 32, 40), anchor="mm")
    path = OUT / "타임줍_로고시안.png"
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
