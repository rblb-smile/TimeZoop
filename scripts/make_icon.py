"""확정 로고(TZ 심볼, packaging/brand/logo_tz_1024.png)로 화면용 PNG와 Windows 아이콘(.ico)을 만든다.

사용: python scripts/make_icon.py
결과: soop_timeline/web/logo.png (512px), soop_timeline/web/app.ico (16~256px)
     → 바탕화면·작업표시줄·설치 파일 아이콘과 프로그램 안 로고가 모두 이 이미지로 바뀐다.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "packaging" / "brand" / "logo_tz_1024.png"
WEB = ROOT / "soop_timeline" / "web"


def main() -> None:
    logo = Image.open(SRC).convert("RGBA")
    logo.resize((512, 512), Image.LANCZOS).save(WEB / "logo.png")
    logo.resize((256, 256), Image.LANCZOS).save(
        WEB / "app.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print("저장:", WEB / "logo.png", WEB / "app.ico")


if __name__ == "__main__":
    main()
