# VideoTextExtractor — 코딩 플랜 (3-Agent 워크플로)

## 에이전트 구성 및 진행 순서

각 마일스톤을 **①코딩 → ②테스트 → ③리팩터** 순서로 통과시킨다.
이전 단계가 완료(체크포인트 기준 충족)되기 전에는 다음 단계를 시작하지 않는다.

| 순서 | 에이전트 | 역할 | 산출물 |
|---|---|---|---|
| 1 | `coder` | 설계 문서(docs/DESIGN.md)에 따라 코드 구현 | 동작하는 모듈 + 최소 자가검증 |
| 2 | `tester` | 테스트 케이스 작성·실행, 실패 보고 | tests/, 테스트 리포트 |
| 3 | `refactorer` | 테스트 통과 유지하며 중복 제거, 구조 개선 | 정리된 코드 + 리팩터링 노트 |

핸드오프 형식: 각 에이전트는 완료 시
`[완료 요약] / [변경 파일 목록] / [다음 에이전트에게 전달 사항] / [검증 방법]` 을 남긴다.

---

## 마일스톤

### M0 — 프로젝트 스캐폴딩 (coder)
- [ ] 패키지 골격: `src/vte/`, `tests/`, `pyproject.toml`, `requirements.txt`
- [ ] `config.py`, `models.py` (TextBox, Track, TextEvent dataclass)
- 체크포인트: `pip install -e .` 성공, 데이터클래스 임포트 가능

### M1 — 프레임 샘플링 + 검출 (coder)
- [ ] `video_reader.py`: fps 샘플링, timestamp 부여
- [ ] `detector.py`: PaddleOCR det 래퍼, 크기/종횡비 필터
- 체크포인트: 샘플 영상에서 bbox 리스트 추출 확인

### M2 — 위치 추적 (coder) ★난제①
- [ ] `tracker.py`: IoU 매칭 + 보조(중심거리) 매칭, EMA 평활화, 트랙 생애주기
- 체크포인트: 인위적 이동 bbox 시퀀스에서 동일 객체가 하나의 트랙으로 유지됨

### M3 — 인식 + 세그먼트 병합 (coder) ★난제②
- [ ] `recognizer.py`: 선명 프레임 선택 → OCR
- [ ] `segmenter.py`: 유사도 병합(≥0.85), gap 메우기(<0.3s), 최소지속 필터(≥0.5s)
- [ ] `postprocess.py`: 텍스트 정규화
- 체크포인트: 동일 자막이 여러 이벤트로 분열되지 않음

### M4 — 출력 + CLI 통합 (coder)
- [ ] `exporter.py`: SRT/JSON/TXT
- [ ] `cli.py`: end-to-end 파이프라인 연결
- 체크포인트: `vte extract sample.mp4 --format all` 동작

### M5 — 실영상 검증 · 튜닝
- [ ] 실제 한국어 영상 2~3종(방송자막/유튜브/강의) 평가
- [ ] 임계값 튜닝, 오류 케이스 백로그 정리

---

## 테스트 전략 (tester 담당)

1. **단위 테스트** (외부 의존성 없이)
   - `models.py`: 데이터클래스 직렬화
   - `segmenter.py`: 합성 입력 시나리오
     - 동일 텍스트 연속 → 단일 이벤트
     - 유사도 경계값(0.84/0.85/0.86)
     - 짧은 gap(0.2s) 병합 / 긴 gap(1s) 분리
     - 최소 지속시간 미달 폐기
     - 서로 다른 위치 동시 자막 → 독립 이벤트
   - `tracker.py`: 가상 bbox 궤적 (정지/이동/깜빡임/교차)
   - `postprocess.py`: OCR 노이즈 문자열 정규화
   - `exporter.py`: SRT 타임코드 포맷 (`00:00:01,500`)
2. **통합 테스트**
   - 합성 영상(PIL/Pillow로 한글 텍스트를 그려 mp4 생성) → end-to-end 실행 →
     기대 구간/텍스트와 비교 (허용 오차 ±0.3s, 유사도 ≥0.9)
   - fixture 생성 스크립트: `tests/fixtures/make_synth_video.py`
3. **골든 테스트**
   - 실영상 1개의 기대 출력(JSON)을 고정해 회귀 방지
4. 실행: `pytest tests/ -v`, 커버리지 `pytest --cov=src/vte`

tester는 실패 발견 시 **수정하지 말고** 재현 절차와 함께 coder에게 전달.

## 리팩터링 원칙 (refactorer 담당)

- 테스트 전부 통과 상태에서만 진행 (녹색이 아니면 시작 금지)
- 대상:
  - Detector/Recognizer 엔진 교체 지점 Protocol 추상화 정리
  - tracker/segmenter의 매직넘버 → config 화
  - 중복 로직 제거, 함수 분리(한 함수 ≤ 30줄 권장)
- 각 마일스톤 종료 시 1회 + M5 후 최종 1회
- 산출: `docs/REFACTOR_NOTES.md`에 변경 요약 누적

## 실행 커맨드 요약

```
@coder "M1 구현: docs/PLAN.md의 M1 항목과 docs/DESIGN.md §4.1–4.2 참조"
@tester "M1 테스트 작성 및 실행"
@refactorer "M1 리팩터"
```
