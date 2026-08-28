"""합성 자막 영상 생성기 (테스트 전용).

- 640x360, 3fps, 12초(36프레임) mp4 (mp4v 코덱)
- 0~3초   : 하단 흰 밴드 + 검정 글자 "첫번째 자막"
- 4~7초   : 같은 위치에 "두번째 자막"
- 8~12초  : 자막 없음

생성물은 저장소에 남기지 않고 pytest tmp_path에만 저장한다.
실행 시간이 수 초~수십 초 걸리는 실엔진 테스트와 달리 이 스크립트 자체는
빠르다(< 1초).
"""
from __future__ import annotations

import sys

import cv2
import numpy as np

WIDTH, HEIGHT, FPS, DURATION = 640, 360, 3.0, 12.0
NUM_FRAMES = int(FPS * DURATION)  # 36

BAND_Y1, BAND_Y2 = 292, 348
_BG_COLOR = (60, 60, 60)
_BAND_COLOR = (255, 255, 255)
_TEXT_COLOR = (0, 0, 0)

_KOREAN_FONTS = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleMyungjo.ttf",
    "/Library/Fonts/NanumGothic.ttf",
]
_FALLBACK_SIZE = 24


def _load_font():
    """한글 폰트를 찾아 (font, used_fallback) 반환. 없으면 영문 기본 폰트."""
    from PIL import ImageFont

    for path in _KOREAN_FONTS:
        try:
            return ImageFont.truetype(path, 30), False
        except OSError:
            continue
    print(
        "WARNING: 한글 폰트를 찾지 못해 영문 기본 폰트로 fallback합니다. "
        "한글 글자가 깨질 수 있습니다.",
        file=sys.stderr,
    )
    return ImageFont.load_default(_FALLBACK_SIZE), True


def make_frame(
    t: float,
    text1: str = "첫번째 자막",
    text2: str = "두번째 자막",
) -> np.ndarray:
    """시각 ``t``(초)의 합성 프레임 1장을 BGR ndarray로 반환."""
    from PIL import Image, ImageDraw

    font, _ = _load_font()
    image = Image.new("RGB", (WIDTH, HEIGHT), _BG_COLOR)
    draw = ImageDraw.Draw(image)

    if t < 3.0:
        text = text1
    elif 4.0 <= t < 7.0:
        text = text2
    else:
        text = ""

    if text:
        draw.rectangle([(0, BAND_Y1), (WIDTH, BAND_Y2)], fill=_BAND_COLOR)
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((WIDTH - tw) / 2 - bbox[0], (BAND_Y1 + BAND_Y2 - th) / 2 - bbox[1]),
            text,
            font=font,
            fill=_TEXT_COLOR,
        )

    arr = np.array(image)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def make_synth(
    path: str,
    text1: str = "첫번째 자막",
    text2: str = "두번째 자막",
) -> str:
    """합성 자막 영상을 ``path``에 저장하고 경로를 반환."""
    writer = cv2.VideoWriter(
        path, cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT)
    )
    if not writer.isOpened():
        raise RuntimeError(f"cannot open VideoWriter for: {path}")
    try:
        for i in range(NUM_FRAMES):
            writer.write(make_frame(i / FPS, text1, text2))
    finally:
        writer.release()
    return path


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "synth.mp4"
    make_synth(out)
    print(f"wrote {out}")
