# Changelog

큰 이정표만 기록한다.

- 2026-08-25: 설계 문서(DESIGN.md), 플랜 v2(PLAN2.md), 유사 프로젝트 조사
  (SOURCE.MD) 완료. 문서 구조를 DX-Manager 방식으로 전환. 에이전트 4종
  (coder/tester/refactorer/benchmarker) 동시 파이프라인 체제 확립.
- 2026-08-25: M0~M1 착수 — 스캐폴딩 및 코어 로직(video_reader,
  scene_detector) 구현 시작.

- 2026-08-25: M0~M4 코어 로직 구현 완료(video_reader, scene_detector,
  tracker, segmenter, filters, preprocess, exporter, cli, pipeline).
  테스트 48개 통과. tester 결함 11건 수정.
- 2026-08-25: README.md 작성. 병렬 창 1 실행: refactorer(tracker/segmenter
  구조 개선, 녹색 유지) + coder(PaddleOCR 3.7 설치·연동 검증 성공,
  detector/recognizer 모델명 고정·크롭 상한 방어) + tester(합성영상 fixture,
  통합테스트 3건 추가 → 51 passed). 결함 1건 신규 보고(동일 위치 연속 자막
  병합 시 텍스트 유실).
- 2026-08-25: 병렬 창 2 — DEFECT-1 해결(crop 내용 변화 감지 재인식 +
  tracker.split/extend_static), DEFECT-2 해결(enhance 2000px 상한),
  UserWarning 제거. 테스트 19건 추가 → 72 passed.
- 2026-08-25: 병렬 창 3 — refactorer(pipeline.py RecognitionCoordinator
  분리), coder(어순 결함 근본 해결: rec 입력 높이 256px 클램프 + 라인 분할
  인식), benchmarker(BENCHMARK.md 생성, det가 병목 ~9.9s/12초 영상).
  어순 결함 재검증: '두번째 자막' 정상 인식. 72 passed 유지.
- 2026-08-25: 실영상 첫 1분 검증(claude.ai UI 녹화, 1080p). fast(mobile
  det) ×5.38배, +roi_band ×2.64배로 개선. server det은 1080p에서 사실상
  불가(30분+ 타임아웃). 한글 하드자막 아닌 한국어 UI 텍스트 검출 확인.
- 2026-08-25: 창6 — det_max_side 도입(fast=mobile+960) + 소형 텍스트
  rec 업스케일(h<48). 재측정: fast ×5.38→×2.64, fast+roi ×2.64→×0.64
  (실시간 돌파, 단 roi+960 조합은 텍스트 붕괴로 프리셋 부적합).
  골든 JSON(tests/golden/first60s.json) 확정, 87 passed.
- 2026-10-09: 창8 — 웹 UI 신설(`vte ui`, 브라우저 실행). stdlib `http.server`
  기반이므로 웹 프레임워크 의존성 없음. 상단 화면 진행(영상/진행바/검출
  박스 오버레이) + 하단 추출 텍스트 레이아웃. Google Flow 풍 디자인 토큰.
  프론트는 `js/core/registry.js` 패널 레지스트리(controls/preview/transcript/
  exporter), 백엔드는 `ui/features/` 기능 라우트 레지스트리(extraction/
  stream/media/export)로 모듈 추가가 각각 한 줄씩. SSE 진행 스트리밍,
  잡 취소, SRT/TXT/JSON/ASS 내보내기 지원. `/api/media`는 Range(206)를
  지원해 브라우저 탐색이 즉각 반응한다. 테스트 31건 추가 → 119 passed.
- 2026-10-10: 세로(portrait) 영상 det 버그 수정 — `det_max_width`(폭 기준
  다운스케일)를 `det_max_side`(긴 변 기준)로 변경. 세로 영상(예: 모바일 화면
  녹화 826x1460)은 폭 826 < 상한 960이라 폭 기준으로는 축소가 아예 스킵되어
  매 프레임을 원본 1460px 높이로 검출하던 문제(프레임당 7.3s)를 긴 변 기준으로
  해결(프레임당 ~3s). 가로 영상(1920x1080)은 폭=최대 변이라 기존 결과와
  동일(회귀 없음, 골든 무손실). CLI 플래그도 `--det-max-side`로 정정.
  detector 옵션 테스트에 portrait 케이스 추가 → 120 passed.
