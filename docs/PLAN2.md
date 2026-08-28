# VideoTextExtractor — 코딩 플랜 v2 (PLAN2.md)

`docs/DESIGN.md` + `docs/SOURCE.MD` 조사 결과를 반영한 개정 플랜.
변경 항목에는 **[v2]** 표기. 3-Agent 워크플로(coder → tester → refactorer)는 동일.

## v2 핵심 변경 요약

1. **[v2] 인식 모델 확정**: `korean_PP-OCRv5_mobile_rec` (정확도 ~90%, PP-OCRv3 한글 60% 대비 대폭 개선, PaddleOCR ≥3.1 필요). 정확도 우선 시 `PP-OCRv5_server_rec` 옵션.
2. **[v2] 장면전환 감지 기반 프레임 스킵**: 정적 구간에서는 검출을 건너뛰어 속도 확보 (VideOCR 방식).
3. **[v2] OCR 다수결 투표**: 트랙당 최선명 프레임 1개 + 상위 N개 선명 프레임 다수결 혼합 (reddol18 기법).
4. **[v2] debounce 강화**: gap 메우기 0.3s → **0.5s 기본**, 신뢰도 임계값(기본 0.9) 필터 추가.
5. **[v2] 이미지 전처리 모듈 신설**: 자동 명암보정, 노이즈 제거, 저해상도 업스케일(옵션), 디인터레이싱(옵션).
6. **[v2] 워터마크·로고 필터 신설**: 영상 전체 지속시간의 X% 이상 존재하는 정적 bbox = 로고로 분류, `--keep-static`으로 유지 선택.
7. **[v2] 추적 업그레이드 경로**: M2는 IoU 그리디로 시작, 실패 케이스 발생 시 SORT(Kalman+헝가리안)로 교체 가능한 구조.
8. **[v2] 실행 모드 3종**: fast / auto / precise (VSE 방식 — 샘플링 fps와 rec 모델 크기 조합).
9. **[v2] UX 보완**: 진행률 출력, `--start/--end` 구간 trim, 배치 처리(디렉토리 입력), 병합 비활성화 옵션(VSE 피드백 반영).

---

## 수정된 아키텍처

```
Video ─▶ FrameSampler ──▶ SceneDetector ──▶ TextDetector ─▶ RegionTracker ─▶ Recognizer
         [v2]장면전환 스킵        │                              ▲        (다수결[v2])
                                  └──▶ Preprocessor[v2] ─────────┘
Segmenter(debounce[v2], 로고필터[v2]) ─▶ Exporter(SRT/TXT/JSON/ASS[v2]) ─▶ CLI(진행률·trim·배치[v2])
```

모듈 추가: `scene_detector.py`(장면전환/프레임 차이), `preprocess.py`(이미지 보정), `filters.py`(로고·워터마크 분류)
모델 버전: PaddleOCR `lang='korean'`, det=`PP-OCRv5_server_det`, rec=`korean_PP-OCRv5_mobile_rec` (config로 교체 가능)

## 마일스톤 (coder)

### M0 — 스캔폴딩
- 패키지 골격, `config.py`에 **[v2]** 실행 모드(fast/auto/precise) 프리셋 포함
- 체크포인트: `pip install -e .`, 데이터클래스 임포트

### M1 — 샘플링 + 장면전환 감지 [확장]
- `video_reader.py`: fps 샘플링 + timestamp
- **[v2] `scene_detector.py`: 프레임 간 해시/히스토그램 차이로 장면전환·정적구간 검출** — 정적 구간은 이후 검출 스킵
- 체크포인트: 합성 영상에서 전환 프레임 인덱스 검출

### M2 — 검출 + 전처리 [확장]
- `detector.py`: PP-OCRv5 det 래퍼, 크기/종횡비 필터
- **[v2] `preprocess.py`: 명암보정(CLAHE), 디노이즈, 업스케일(x2, 옵션)** — det/rec 입력 전 적용
- 체크포인트: 샘플 bbox 추출, 저대비 합성영상에서 전처리 on/off 비교

### M3 — 위치 추적 ★난제①
- `tracker.py`: IoU 매칭(≥0.5) + 중심거리 보조, EMA 평활화
- **[v2] 매칭 알고리즘을 Protocol로 분리** → SORT 교체 경로 확보 (테스트에서 ID-switch 발생 시 착수)
- 체크포인트: 가상 궤적에서 트랙 유지

### M4 — 인식 + 세그먼트 ★난제②
- `recognizer.py`: **[v2] korean_PP-OCRv5_mobile_rec**, 선명 프레임 + 상위 N프레임 **다수결 투표**, 신뢰도 <0.9 폐기 옵션
- `segmenter.py`: 유사도 병합(≥0.85), **debounce 0.5s 기본**, min_duration 0.5s
- **[v2] `filters.py`: 로고 필터 — 트랙 지속시간 > 전체의 80% && 위치 고정 → 로고 분류**
- **[v2] `--no-merge` 옵션**: 같은 텍스트라도 연속 병합 금지 (VSE 사용자 피드백)
- `postprocess.py`: 정규화
- 체크포인트: 동일 자막 단일 이벤트 유지, 로고 제거 확인

### M5 — 출력 + CLI 통합 [확장]
- `exporter.py`: SRT/TXT/**JSON(bbox+confidence)**/**ASS**
- `cli.py`: end-to-end + **[v2] 진행률(tqdm), --start/--end trim, 배치(디렉토리), --mode fast|auto|precise**
- 체크포인트: `vte extract sample.mp4 --format all --mode auto`

### M6 — 실영상 검증 · 벤치마크 [신규]
- 한국어 실영상 2~3종 평가, **[v2] 처리속도 측정**(45분 영상 목표: CPU fast 모드 ≤ 실시간의 2배)
- VSE/VideOCR 결과와 수동 비교 리포트 작성

## 테스트 전략 (tester) — v2 추가분

기존 전략 유지. 추가:
1. `scene_detector.py`: 정지 컷/전환 컷 합성 시나리오, 임계값 경계
2. `preprocess.py`: 어두운/저해상도 합성 입력에서 OCR mock 통과율
3. `filters.py`: 80% 경계(79%/81%) 로고 판정
4. `recognizer.py`: 다수결 로직 — 3프레임 중 2개 동일 답 선택, 전부 다르면 최고신뢰도 선택
5. 통합 fixture: 깜빡임(0.4s gap → 병합됨 / 0.6s gap → 분리됨) 시나리오 추가
6. 성능 회귀: 장면전환 스킵 on/off 처리 프레임 수 비교 (스킵 시 유의미한 감소 확인)

## 리팩터 원칙 (refactorer) — 변경 없음

docs/PLAN.md 원칙 동일: 녹색 테스트에서만 착수, 매직넘버 config 화, `docs/REFACTOR_NOTES.md` 누적.

## 향후 백로그 (M7+, 설계 확정 후 별도 플랜)

- SORT(Kalman+헝가리안) 추적기 도입 — M3에서 ID-switch 문제 확인 시
- VLM 백엔드(Ollama qwen-vl 등) Recognizer 추가 — 간섭 심한 화면용 (SOURCE.MD §1.6)
- Google Lens/CLOVA 등 클라우드 하이브리드 인식 (VideOCR google_lens 모드 참고)
- GUI 또는 웹 UI, 스크롤 티커 추적
