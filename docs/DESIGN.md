# VideoTextExtractor — 설계 문서

영상에서 한국어 텍스트(자막·타이틀·화면 삽입글)를 추출하는 프로그램.

## 1. 목표 및 입출력

- **입력**: 영상 파일 (mp4, mkv, avi 등)
- **출력**:
  - 텍스트 존재 구간 리스트: `[ {start, end, bbox[], text} ]` (JSON / SRT / TXT)
- **핵심 요구사항**
  1. 글자가 보이는 화면의 **타임 구간** 검출 → 리스트화
  2. 해당 구간의 화면 글씨를 **텍스트로 출력** (한국어 기준)
  3. 어려운 문제 2가지 해결:
     - 텍스트 **위치 추적** (프레임 간 위치 변동)
     - 같은 내용이 지속될 때의 **중복 제거**

## 2. 참조 프로젝트 분석

| 항목 | MakehardSub | videoTotext |
|---|---|---|
| 방식 | 자막 영역 수동 지정(--pos) → 프레임 비교로 타임코드 추출 → Tesseract OCR | OpenCV 전처리(6단계) + CNN으로 글자 여부 판별 → Tesseract OCR |
| 한계 | 자막 위치를 사용자가 직접 지정해야 함 | Tesseract 한글 인식률 낮음, 딥러닝 모델 학습 필요 |

**본 설계의 개선점**: 딥러닝 기반 장면 텍스트 검출(PaddleOCR det)으로 **위치 자동 검출**, 한글 특화 인식기(korean rec) 사용, 시간축 병합으로 중복 제거.

## 3. 기술 스택

- Python 3.10+
- OpenCV (`opencv-python`) — 프레임 추출
- PaddleOCR (`paddleocr`, `paddlepaddle`) — 텍스트 검출(det) + 한글 인식(rec, `lang='korea'`)
  - 대안: EasyOCR(`ko`), CLOVA OCR API (유료, 정확도 최상). 인터페이스를 추상화하여 교체 가능하게 설계.
- rapidfuzz — 텍스트 유사도 (중복 판정)
- pytest — 테스트

## 4. 파이프라인 아키텍처

```
Video ─▶ FrameSampler ─▶ TextDetector ─▶ RegionTracker ─▶ Recognizer
                                                          │
                          Segmenter(시간구간 병합·중복제거) ◀┘
                                    │
                              Exporter ─▶ SRT / JSON / TXT
```

### 모듈 구성

```
src/vte/
├── cli.py            # argparse 진입점
├── config.py         # dataclass 설정 (샘플링 fps, 임계값 등)
├── models.py         # TextBox, TextEvent 등 데이터클래스
├── video_reader.py   # 프레임 샘플링 (기본 2~5 fps)
├── detector.py       # 텍스트 영역 검출 (PaddleOCR det 래퍼)
├── tracker.py        # 프레임 간 영역 추적 (IoU 기반)
├── recognizer.py     # OCR 인식 (PaddleOCR rec 래퍼, 엔진 교체 가능)
├── segmenter.py      # 시간 구간 생성 + 중복 제거 + gap 병합
├── postprocess.py    # 텍스트 정규화 (공백/특수문자, 한글 조사 정리)
└── exporter.py       # SRT / JSON / TXT 출력
```

### 4.1 FrameSampler
- `fps=N`으로 균등 샘플링 (기본 3fps — 자막 최소 노출 ~1초 가정).
- 각 프레임에 timestamp 부여.

### 4.2 TextDetector (위치 검출)
- PaddleOCR `det` 모델로 프레임 내 모든 텍스트 bbox 검출.
- 옵션: 관심 영역(ROI) 지정 시 하단 밴드 우선(자막 휴리스틱), 미지정 시 전체 화면.
- 필터: 최소/최대 크기, 종횡비로 노이즈(로고·워터마크는 후속 단계에서 지속성 필터로 걸러냄).

### 4.3 RegionTracker (위치 추적 — 난제 ①)
- 프레임 t와 t+1의 bbox를 **IoU ≥ 0.5** 로 매칭하여 트랙(track) 형성.
- 자막의 미세한 흔들림 대비:
  - IoU 매칭 실패 시 중심점 거리 + 크기 유사도 보조 매칭
  - 트랙별 EMA로 bbox 평활화
- 트랙 생애주기: 신규 생성 / 유지 / 종료(max_missed 프레임 초과 시).
- 멀티 영역 동시 지원 (하단 자막 + 상단 타이틀 동시 처리).

### 4.4 Recognizer
- 트랙의 대표 프레임(선명도 Laplacian variance 최대 프레임) crop → OCR.
- 트랙 전체를 매 프레임 OCR하지 않아 속도 확보. (옵션: N프레임마다 재인식 후 다수결)

### 4.5 Segmenter (시간 구간 + 중복 제거 — 난제 ②)
1. 각 트랙 = 하나의 후보 이벤트 `{start, end, bbox, text}`.
2. **같은 내용 지속 병합**: 연속 트랙들의 텍스트가 `rapidfuzz similarity ≥ 0.85`(정규화 후)이면 동일 이벤트로 병합.
3. **깜빡임(gap) 메우기**: 같은 텍스트 이벤트 사이 갭 < `min_gap`(기본 0.3s)이면 하나로 연결.
4. **짧은 노이즈 제거**: 지속시간 < `min_duration`(기본 0.5s) 이벤트 폐기 (워터마크·로고는 수십 초 지속되므로 옵션으로 별도 필터링 가능).
5. 겹치는 서로 다른 위치의 이벤트는 독립 유지.

### 4.6 Postprocess
- OCR 노이즈 정리: 불필요 공백/개행, 반복 특수문자, 한글 외 잔여 문자 필터(옵션).
- 흔한 OCR 오류 치환 테이블 (선택).

### 4.7 Exporter
- JSON: 원본 구조 보존 (`{start, end, bboxes, text}`)
- SRT/VTT: 자막 호환
- TXT: 줄바꿈 나열

## 5. 핵심 데이터 모델

```python
@dataclass
class TextBox:
    pts: list[tuple[float, float]]  # 4-corner polygon
    score: float

@dataclass
class Track:
    id: int
    boxes: dict[int, TextBox]   # frame_idx -> box
    texts: list[str]            # 인식 결과 누적
    start_ts: float
    end_ts: float

@dataclass
class TextEvent:
    start: float
    end: float
    text: str
    bboxes: list[TextBox]
```

## 6. CLI 인터페이스

```
vte extract VIDEO [--fps 3] [--roi L,T,W,H] [--lang ko]
                  [--sim-threshold 0.85] [--min-gap 0.3] [--min-duration 0.5]
                  [--format srt|json|txt|all] [--output out]
vte intervals VIDEO [...]          # 구간 리스트만 출력
vte ocr VIDEO --ref times.json     # 주어진 구간만 OCR
```

## 7. 성능·품질 전략

- 속도: 프레임 다운스케일 후 det, GPU 선택적(paddle device), 트랙당 1회 인식.
- 정확도: 선명 프레임 선택 + 다중 프레임 투표(옵션) + 유사도 기반 병합.
- 확장성: Recognizer/Detector를 Protocol(ABC)로 추상화 → CLOVA API 등 교체 용이.
