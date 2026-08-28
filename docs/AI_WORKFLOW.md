# AI Workflow

## 시작

1. `AGENTS.md`의 작업 시작 절차를 따른다.
2. 가상환경: `python3 -m venv .venv && source .venv/bin/activate`

## 빌드/설치

```bash
pip install -e ".[dev]"        # 패키지 + pytest 등 개발 의존성
pip install -r requirements.txt  # paddlepaddle/paddleocr 포함 (무거움, 선택)
```

PaddleOCR은 `requirements.txt`에서 별도 관리한다. 엔진 미설치 환경에서도
`pytest tests/ -v`의 코어 로직 테스트는 통과해야 한다(detector/recognizer는
lazy import).

## 검증 명령

```bash
pytest tests/ -v               # 전체 단위 테스트
pytest tests/ -v --cov=src/vte # 커버리지
vte extract sample.mp4 --format json   # CLI 스모크 (샘플 필요)
```

## 문서 갱신 규칙

- 모든 작업 종료 시: `docs/SESSION.md`(자기 섹션), `docs/TODO.md`(체크박스)
- 동작 변경 시: DECISIONS/TECH_NOTES/KNOWN_ISSUES 해당 문서
- 마일스톤 완료 시: `docs/CHANGELOG.md` 한 줄 추가
