# Project Brief

## 목표

영상 파일에서 한국어 화면 텍스트(자막·타이틀·삽입글)를 추출해
시간 구간 리스트와 텍스트(SRT/TXT/JSON/ASS)로 출력하는 CLI 프로그램.

## 핵심 기능

1. 글자가 보이는 타임 구간 검출 → 리스트화
2. 구간 내 텍스트 OCR (한국어 기준)
3. 난제 해결: 프레임 간 텍스트 위치 추적(IoU+보조매칭), 중복 제거(유사도
   병합 + debounce + 로고 필터)

## 비목표 (현재)

- GUI, 스크롤 티커 추적, 음성인식(STT), 번역 — 백로그로 분리
- Windows/GPU 최적화 빌드

## 기술 스택

Python 3.10+, OpenCV, PaddleOCR(korean_PP-OCRv5_mobile_rec), rapidfuzz,
pytest. OCR 엔진은 추상화되어 교체 가능(EasyOCR/CLOVA/VLM).

## 진행 방식

`PLAN2.md` 마일스톤 M0~M6을 4개 에이전트(coder/tester/refactorer/
benchmarker)가 파이프라인으로 동시 진행한다. `AGENTS.md` 참조.
