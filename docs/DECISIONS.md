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

## D6. 웹 UI는 표준 라이브러리 `http.server` + ES 모듈로 구현 (2026-10-09)

- **선택지**: ① 데스크톱 GUI(tkinter/PySide) ② 웹 프레임워크(Gradio/Streamlit/FastAPI) ③ 표준 라이브러리 웹 서버. ③을 택했다.
- 근거: 배포 대상은 "CPU 우선"의 범용 환경이다. ①은 원격/헤드리스 실행에서 무의미하고 의존성이 크다. ②는 서버 실행 시 자동으로 끌어오는 무거운 스택(및 버전 고정 리스크)이 생기고, 파이프라인과 엔진을 이미 격리해 둔 구조와 맞지 않는다. ③은 `http.server` + `threading`만으로 SSE·정적 파일·Range 요청(영상 스트리밍)을 모두 처리할 수 있어 **의존성 추가 0**이다.
- **영상 미리보기는 HTTP Range 스트리밍**으로 구현했다. 프레임을 PNG로 인코딩해 밀어넣는 방식은 서버 메모리와 인코딩 비용이 크고 탐색(seek)이 느리다. `<video src="/api/media?path=...">` 한 줄로 브라우저가 직접 디코딩하게 하면 스크럽이 즉각 반응한다.
- **프론트/백엔드 모두 레지스트리 패턴**으로 모듈 추가 비용을 한 줄로 고정했다. 패널은 `{name, mountPoint, mount(el, App)}`, 기능 라우트는 `register(router, app)` 계약이며 코어를 수정하지 않는다.
- **디자인은 Google Flow 계열 토큰**(어두운 표면, 글래스 패널, 청→보라 그라데이션)으로 통일. `app.css`의 `:root` 변수 집합이 단일 진실 공급원이다.

