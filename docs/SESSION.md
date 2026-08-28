## 현재 상태

- **M0~M6 완료.** 실영상 1분 클립 기준 end-to-end 검증·벤치마크 완료
- 1분 테스트 클립: `claude_first60s.mp4` (저장소 루트, 3.9MB)
- 성능 (claude_first60s, CPU i9, OMP_NUM_THREADS=8):
  - fast(mobile+960): **×2.64** — 골든 20개 이벤트 무손실 재현
  - fast+roi+960: **×0.64 (실시간 돌파)** — 단 텍스트 붕괴('지침 저 -')로 프리셋 부적합
  - server det: 1080p 원본 불가 → det_max_width=1280으로 회복(~65s/frame)
- 소형 텍스트 rec 개선(h<48 업스케일): '오늘 어떤 도움을 드릴까요? [0.95]' 수준 회복
- 골든 JSON: `tests/golden/first60s.json` (fast 모드, 20 이벤트, 결정적 재현 확인)
- 테스트: **88 passed + 1 skipped** (골든 라이브 비교는 VTE_GOLDEN_LIVE=1 게이트)

## 에이전트 창 이력

| 창 | coder | tester | refactorer | benchmarker |
|---|---|---|---|---|
| 1 | M0~M4 코어 | 48테스트, 결함11건 | — | — |
| 2 | 엔진 연동 | fixture+통합, DEFECT-1 보고 | tracker/segmenter | — |
| 3 | DEFECT-1·2 해결 | +19 테스트(72) | — | — |
| 4 | 어순 결함 근본 해결 | — | pipeline 분리 | BENCHMARK.md 생성 |
| 5 | mobile det + roi_band | integration 정리+split 테스트(83) | Track 인계 구조 | 실영상 첫 1분 검증 |
| 6 | det_max_width + 소형rec 개선 | detector 규약 + 골든 JSON(87) | — | 재측정 ×0.64 |
| 7 | ASS 타임스탬프 + rec 48px/2000px cap + score 합성 | +1 테스트 (88) | — | — |

## 남은 과제

1. **골든 유지보수 규칙**: det/rec 옵션 변경 창에서는 골든 재캡처 또는 VTE_GOLDEN_LIVE=1 실행 (tester 메모)
2. **백로그**: SORT 추적기, VLM 백엔드, GUI 등 (TODO.md)

## 다음 창 지시 사항

- coder: 실영상 roi+960 조합 벤치마크 검증 및 추가 튜닝 ∥
- tester: VTE_GOLDEN_LIVE=1 라이브 골든 회귀 테스트 ∥
- refactorer: 대기 (안정화 유지)

