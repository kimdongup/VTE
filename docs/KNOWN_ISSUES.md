# Known Issues

알려진 제약과 미해결 문제. 확인된 것만 기록한다.

- [제약] PaddleOCR 미설치 환경에서 detector/recognizer 관련 통합 테스트는
  skip된다 (lazy import 설계 — 의도된 동작).
- [미해결] 회전·기울어진 텍스트의 IoU 추적 정밀도 — axis-aligned 변환으로
  인한 오차 가능. M3 실영상 검증에서 재평가.
- [미해결] 워터마크가 화면 전체의 80% 미만만 등장하는 경우 로고 필터를
  통과한다. 사용자 ROI 지정으로 우회 가능.
