# TODO

우선순위 순. 각 에이전트는 완료 시 자기 항목의 체크박스만 갱신한다.

## 다음 작업

- [x] M0 스캐폴딩 (coder)
  - [x] pyproject.toml, requirements.txt, 패키지 골격
  - [x] config.py (fast/auto/precise 프리셋), models.py
- [x] M1 샘플링 + 장면전환 감지 (coder)
  - [x] video_reader.py: fps 샘플링 + timestamp
  - [x] scene_detector.py: 정적/전환 프레임 판정
- [x] M1 테스트 (tester)
  - [x] test_models / test_scene_detector / test_video_reader 관련 단위 테스트
- [x] M3 위치 추적 ★난제① — tracker.py 구현 + 6개 테스트 통과 (선행 완료)
- [x] M4 세그먼트 병합 ★난제② — segmenter/filters/postprocess + 테스트 통과
- [x] M2 검출 + 전처리 — PaddleOCR 3.7 실엔진 연동 검증 완료 (2026-08-25)
- [x] M5 출력 + CLI 통합 — CLI/통합/엔진 계약 테스트 통과 (2026-08-25)
- [x] M6 벤치마크
  - [x] 합성 영상 12초 3모드 측정 완료 → docs/BENCHMARK.md (2026-08-25 benchmarker)
  - [x] 실영상 첫 1분 검증 (2026-08-25): fast ×5.38 → 개선 후 재측정 완료
  - [x] coder det 개선 후 동일 구간 재측정: fast(mobile+960) ×2.64(2배 향상),
        fast+roi+960 **×0.64 실시간 돌파** — 단 roi+960 텍스트 붕괴로 프리셋 부적합
- [x] 리팩터: tracker/segmenter(창1), pipeline RecognitionCoordinator 분리(창3),
      Track 인계 구조(starting/close_track)(창5)
- [x] det 병목 개선: fast=PP-OCRv5_mobile_det + roi_band + det_max_width (창5~6)
- [x] 소형 텍스트 rec 품질 개선 — crop h<48 업스케일 ('오늘 어떤 도움을 드릴까요?' 회복)
- [x] **roi 조합 품질 붕괴 해소** — line target height 48px 및 min height 방어 적용 (창7)
- [x] rec crop 폭 캡 — paddle max_side_limit 4000 경고 해소 및 _normalize_line w<=2000 클램프 (창7)
- [x] ASS exporter 타임스탬프 계산 수식 정정 (창7)
- [x] confidence 투표 비율 + 개별 OCR score 노출 합성 (창7)
- [x] test_integration.py의 scene_threshold 우회 제거 + mock 내용 매핑화 (창5)
- [x] 회귀 보강: tracker.split/extend_static 단위테스트, crop 변화 회귀 (창5)
- [x] 실영상 첫 1분 골든 JSON 고정 — tests/golden/first60s.json, 20 이벤트 (창6)
- 백로그: SORT 추적기, VLM 백엔드, 클라우드 OCR 하이브리드, GUI, 스크롤 티커

## 결함 보고 (tester → coder)

- ~~11건 보고~~ → 2026-08-25 창에서 전부 수정 확인 (SESSION.md 참조)
- [2026-08-25 tester] 동일 위치 연속 자막 병합 시 텍스트 유실 — **해결됨 (2026-08-25 coder)**
  - 수정: pipeline이 활성 트랙의 crop을 내용 변화 시마다 재인식하고,
    직전 확정 텍스트와 rapidfuzz ratio가 `sim_threshold` 미만이면 트랙을
    강제 종료하고 같은 밴드로 새 트랙을 시작 (`tracker.RegionTracker.split`).
  - 검증: 기본 `Config()`에서 이벤트 2개 확인
    (`tests/test_defect_regression.py` xpass, 실엔진 수동 실행도 2개).
  - 재현: `tests/fixtures/make_synth_video.py` 합성 영상(0~3초 "첫번째
    자막", 4~7초 "두번째 자막", 동일 위치 하단 밴드)에 대해
    `TextDetector.detect`가 고정 bbox를 반환하도록 mock 걸고 기본 `Config()`로
    `pipeline.run_extract` 실행 → 이벤트 1개(`start=0.0, end≈4.33,
    text="첫번째 자막"`)만 나옴. 기대는 2개.
  - 원인: tracker가 bbox IoU/중심거리만 보고 매칭하므로 위치가 같은 서로 다른
    자막이 한 트랙으로 합쳐지고, pipeline은 트랙당 recognize를 1회만 호출해
    최선 crop 1장의 텍스트만 반영함. 뒤 자막 텍스트가 소실.
  - 참고: 통합 테스트(`tests/test_integration.py`)는 `scene_threshold=-1.0`으로
    매 샘플 처리 + 자막 공백 구간(3~4초, 7~8초)에서 `max_missed` 초과 만료로
    트랙을 분리해 우회 검증함. 근본 해결 필요(예: 밴드 픽셀 변화 감지 시
    강제 트랙 분리, 또는 트랙별 복수 crop 인식·타임스탬프별 세그먼트화).
