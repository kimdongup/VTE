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
- 2026-08-25: 창6 — det_max_width 도입(fast=mobile+960) + 소형 텍스트
  rec 업스케일(h<48). 재측정: fast ×5.38→×2.64, fast+roi ×2.64→×0.64
  (실시간 돌파, 단 roi+960 조합은 텍스트 붕괴로 프리셋 부적합).
  골든 JSON(tests/golden/first60s.json) 확정, 87 passed.
