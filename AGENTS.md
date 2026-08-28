# VideoTextExtractor (VTE) agent guidance

이 파일은 저장소 전체에 적용되는 에이전트 작업 규칙이다. 진행 상태처럼 자주
바뀌는 정보는 이 파일에 두지 않고 `docs/SESSION.md`, `docs/TODO.md`에서
관리한다.

## 작업 시작

1. `docs/README.md`, `docs/PROJECT_BRIEF.md`, `docs/SESSION.md`,
   `docs/TODO.md`를 읽는다.
2. 설계는 `docs/DESIGN.md`, 실행 플랜은 `docs/PLAN2.md`, 유사 프로젝트
   조사는 `docs/SOURCE.MD`를 기준으로 한다.
3. 구현 세부는 `docs/TECH_NOTES.md`, 설계 결정 사유는 `docs/DECISIONS.md`,
   알려진 제약은 `docs/KNOWN_ISSUES.md`를 확인한다.
4. 빌드·검증 명령은 `docs/AI_WORKFLOW.md`를 따른다.

## 에이전트 구성과 동시 실행

에이전트는 순차가 아니라 **소프트웨어 파이프라인**으로 동시 작동한다.
마일스톤 n 기준 동시 창:

| 에이전트 | 시점 n에서의 작업 | 충돌 영역 |
|---|---|---|
| `coder` | M(n) 구현 | `src/vte/**` |
| `tester` | M(n-1) 테스트 작성·실행 | `tests/**` |
| `refactorer` | M(n-2) 리팩터 | `src/vte/**` (녹색 테스트에서만) |
| `benchmarker` | M6 도달 시 실영상 성능 측정 | `docs/BENCHMARK*.md`, 임시 산출물 |

동시성 규칙:
- 파일 소유권 분리로 충돌을 방지한다. coder와 refactorer가 같은 모듈을 동시에
  고치지 않게 하기 위해, refactorer는 항상 2단계 뒤의 마일스톤만 다룬다.
- tester가 실패를 발견하면 운영 코드(`src/`)를 고치지 않고 결함 보고를
  남긴다. coder는 다음 창에서 해당 결함 수정을 최우선 과제로 수행한다.
- 공유 문서(`docs/SESSION.md`, `docs/TODO.md`)는 각 에이전트가 종료 시
  자신의 섹션만 갱신한다.

## 협업 및 수정 원칙

- 사용자가 검토·진단·원인 파악을 요청하면 파일을 수정하지 않는다.
- 요청 범위에 필요한 최소 변경만 하며 기존 기능과 미커밋 변경을 보존한다.
- 추측을 사실로 기록하지 않는다. 재현되지 않은 문제를 확인된 버그로 단정하지
  않는다.
- 관련 없는 리팩터링, 새 의존성 추가를 함께 넣지 않는다.
- PaddleOCR 같은 외부 엔진 의존은 `detector.py`/`recognizer.py` 내부로만
  격리한다. 다른 모듈이 직접 임포트하지 않는다.

## 지원 환경과 불변 조건

- Python 3.10+, 개발 환경은 macOS, 배포 대상은 CPU 우선(GPU 선택적).
- OCR: PaddleOCR ≥3.1, rec=`korean_PP-OCRv5_mobile_rec`, det=PP-OCRv5 계열.
- 프레임 샘플링·추적·세그먼트 로직은 OpenCV/numpy/rapidfuzz만 사용하며
  딥러닝 엔진 없이 단위 테스트 가능해야 한다.
- 출력 포맷: SRT/TXT/JSON(bbox+confidence)/ASS.
- 한글 텍스트가 기준. 언어 교체는 설정으로만 가능하게 유지한다.

## 검증

- 모든 로직 변경 후 `pytest tests/ -v` 통과를 확인한다.
- CLI 변경 후 `vte extract <샘플> --format json` 스모크 테스트를 돌린다.
- 실영상 검증은 benchmarker가 담당하며 결과를 `docs/BENCHMARK.md`에 기록한다.

## Git, 문서 관리

- commit은 사용자가 요청한 경우에만 수행한다. 한 커밋에는 한 목적만 담는다.
- 동작·제약이 바뀌면 관련 문서를 즉시 갱신한다: 설계 결정은
  `docs/DECISIONS.md`, 구현 세부는 `docs/TECH_NOTES.md`, 새 제약은
  `docs/KNOWN_ISSUES.md`, 할 일은 `docs/TODO.md`, 세션 상태는
  `docs/SESSION.md`, 이정표는 `docs/CHANGELOG.md`.
