# Decisions

설계 결정과 사유를 기록한다. 최신이 아래에 추가된다.

## D1. OCR 엔진: PaddleOCR korean_PP-OCRv5_mobile_rec (2026-08-25)

- v3 한글 모델(60.21%) 대비 v5 한글 mobile(~88~90%)로 정확도 대폭 개선.
- mobile 우선(CPU 속도), 정확도 필요 시 server_rec로 교체 — config에서만 변경.
- 근거: docs/SOURCE.MD §2, PaddleOCR 공식 문서.

## D2. 장면전환 감지 기반 프레임 스킵 (2026-08-25)

- 정적 구간 재검출을 건너뛰어 처리량 절감 (VideOCR 방식).
- 프레임 차이는 해시/히스토그램 비교로 구현, 딥러닝 불필요.

## D3. 중복 제거 3단 구성 (2026-08-25)

1. 트랙 = 이벤트 (위치 추적 결과)
2. 유사도 ≥0.85 병합 + debounce gap <0.5s 메우기
3. min_duration <0.5s 폐기 + 전체지속 >80% 정적 bbox 로고 분류

단일 임계값보다 단계별 필터가 오탐/미탐 조정이 쉽다.

## D4. 엔진 격리 (2026-08-25)

PaddleOCR은 detector.py/recognizer.py 내부 lazy import만 허용. 코어 로직은
numpy/OpenCV만으로 테스트 가능하게 유지 → CI와 엔진 교체(EasyOCR/VLM) 대응.

## D5. ASS 타임스탬프 밀리초/센티초 단위 정정 및 Rec 라인 타깃 높이 48px 고정 (2026-08-28)

- ASS 수출기(`_ts_ass`)의 센티초(cs) 단위 계산 수식 정정 (1시간 = 360,000 cs, 1분 = 6,000 cs).
- `recognizer.py` line normalization 타깃 높이를 48px로 고정하고 `_clamp_size`에서 폭(w) 클램핑 시 최소 높이 48px를 보장하여 PaddleOCR `max_side_limit(4000)` 경고 및 와이드 자막/UI 텍스트 붕괴 현상 근본 해소.
- `best_text`에서 투표 비율과 실엔진 OCR 스코어(`track.scores`)를 결합하여 유의미한 `confidence` 반환.

