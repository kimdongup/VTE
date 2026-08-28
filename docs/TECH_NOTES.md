# Tech Notes

구현 세부를 누적 기록한다.

## 데이터 흐름

FrameSample(ts, frame) → SceneDetector(변화 판정) → TextDetector(bbox 목록)
→ RegionTracker(Track 누적) → Recognizer(텍스트+confidence)
→ Segmenter(TextEvent 목록) → Exporter

## 핵심 파라미터 (config.py)

| 파라미터 | 기본값 | 근거 |
|---|---|---|
| sample_fps | 3 | 자막 최소 노출 ~1s 가정 |
| iou_threshold | 0.5 | SORT 계열 관행 |
| sim_threshold | 0.85 | rapidfuzz ratio |
| debounce_gap | 0.5s | VideOCR debounce 범위 하한 |
| min_duration | 0.5s | VSE 관행 |
| logo_ratio | 0.8 | 영상의 80% 이상 지속 시 로고 |
| conf_threshold | 0.9 | VideOCR 기본 |

## 좌표계

bbox는 4-corner polygon `(x, y)` float 리스트. IoU 계산 시 axis-aligned
bounding rect로 변환한다(회전 텍스트는 후순위).

## lazy import 패턴

`detector.py`, `recognizer.py`는 함수 내부 `from paddleocr import PaddleOCR`
형태. ImportError 시 명확한 안내 메시지를 raise한다.

## Engine smoke (2026-08-25)

- 설치: `paddlepaddle==3.0.0`, `paddleocr==3.7.0` (paddlex 3.7.2 동반).
  PyPI의 macOS x86_64용 paddlepaddle은 3.0.0이 최신.
- 호환성 이슈: paddleocr 3.x는 det/rec 모델명을 일부만 지정하면 나머지에
  기본 v6 모델(PP-OCRv6_medium_det/rec)을 쓰는데, 이 모델들은
  paddlepaddle 3.0.0 static inference에서
  `InvalidArgument: Type of attribute: strides is not right` 로 로드 실패한다.
  → detector/recognizer 모두 det·rec 모델명을 **둘 다** 명시 고정하고,
  `use_doc_orientation_classify=False`, `use_doc_unwarping=False` 로 문서
  전처리 모델(doc_ori, UVDoc)을 비활성화했다(영상 자막에는 불필요, 로딩 절약).
- 결과 파싱: paddleocr 3.x의 `predict()`는 paddlex `OCRResult`(dict 계열)를
  반환하며 기존 파싱 키(`dt_polys`, `dt_scores`, `rec_texts`, `rec_scores`)가
  그대로 유효했다. 단 `dt_scores`는 존재하지 않을 수 있어 기본값 1.0 폴백 유지.
  참고: 실제 응답에 dt score 키는 `dt_polys`와 별도 `dt_scores`로 온다.
- 스모크 결과(1280x720 합성 이미지, "Hello VTE 2026"): 검출 box 1개,
  인식 `Hello VTE 2026` / score 0.9998.
- 성능 함정: `preprocess.enhance()`가 작은 크롭(예: 높이 75px)을 720px까지
  2배씩 올리며 최대 16배 업스케일할 수 있고, 그 결과(8208x1200)를 rec 엔진에
  넣으면 paddlex의 max_side_limit(4000) 리사이즈 경로가 CPU에서 수 분 소요된다.
  → recognizer.py 입력단에서 longest side > 2000이면 INTER_AREA로 선제 축소하는
  방어 코드를 추가했다. 근본 해결(enhance의 업스케일 상한)은 preprocess.py
  개선 과제로 tester/refactorer에게 전달.
- 환경 변수: 모델 호스터 연결 확인이 느릴 수 있으므로
  `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True` 권장(모델은
  `~/.paddlex/official_models/`에 캐시됨).

## 동일 위치 연속 자막 분리 (2026-08-25 coder 구현 노트)

- pipeline.run_extract는 이제 트랙당 1회가 아니라 **crop 내용이 변했을 때마다**
  재인식한다. 변화 판정은 crop을 128x32 그레이스케일 썸네일로 축소해 평균절차차
  (MAD/255)를 계산, `_CROP_CHANGE_THRESHOLD=0.003` 미만이면 동일 내용으로
  간주하고 OCR을 건너뛴다. 합성 픽스처 기준 실측: 정적 내용 재인식 시 노이즈
  0.0, 자막 교체 신호 ~0.008이므로 여유를 양쪽으로 둔 값이다.
- 새 텍스트의 rapidfuzz ratio가 직전 확정 텍스트와 `sim_threshold` 미만이면
  `RegionTracker.split()`으로 현재 트랙을 종료 처리(finished 목록)하고 같은 박스의
  새 트랙(새 id, start_ts=현재 ts)을 시작한다. 구 트랙 end_ts는 샘플 간격
  (1/sample_fps) 하나 앞으로 당겨 경계를 근사한다. 종료된 트랙은 기존과 동일하게
  segmenter.build_events/drop_logos 흐름에 들어간다.
- scene skip 구간(정적 프레임)에서는 `RegionTracker.extend_static(ts)`로
  healthy(미싱 아님) 트랙의 end_ts를 연장한다. 이걸 빼먹으면 정적 자막이
  min_duration 미만으로 잘려 폐기되므로 필수. missed 상태 트랙은 연장하지 않는다.
- 인식 결과가 빈 문자열/비한글이면 시그니처를 갱신하지 않아 다음 처리 샘플에서
  재시도한다(한 번의 나쁜 판독으로 내용이 잠기지 않게 함).
- recognize mock 대응 메모(tester용): 인식 호출은 "내용 변화 시 1회"이므로
  트랙당 정확히 1회가 아니다. 순서 기반 iterator mock은 유지 가능하지만
  호출 횟수 가정을 바꿔야 한다.
- preprocess.enhance는 2배 누적 대신 `min(720/h, 2000/max(h,w))` 배율 한 번에
  리사이즈하도록 바꿨다. 최장 변 2000px 하드 상한(`_MAX_UPSCALED_SIDE`) 도입.
  recognizer 입력단 방어 축소 코드는 공개 API 방어로 유지.
- detector/recognizer 모두 모델명 명시 시 paddleocr에 `lang`을 넘기지 않게
  해서 "`lang` and `ocr_version` will be ignored" UserWarning 제거.
  `cfg.lang`은 설정값으로 남아 있다(엔진 기본 lang은 모델명이 결정).
- 알려진 한계: 실엔진 수동 검증에서 두 번째 자막이 "자막 째 번 두"로 어순이
  뒤섞여 인식됨(넓은 밴드 crop + rec 모델 특성으로 추정). 트랙 분리·타이밍은
  정상이므로 인식 품질 문제로 분리해 후속 과제(benchmarker/refactorer)로 남김.

## Rec line-split (2026-08-25)

- 증상 재정의: 어순 뒤섞임은 2줄 밴드뿐 아니라 **단일 라인 crop의 과도한
  업스케일**에서도 발생한다. `korean_PP-OCRv5_mobile_rec` 실측(합성 픽스처
  "두번째 자막", 원본 높이 40px):
  - 높이 ≤256px → 정상 ("두번째 자막", conf ≥0.999)
  - 높이 ≥288px → 어순 뒤바뀜 ("자막 두번째" / "자막 째 번 두", conf ≥0.999)
  - 즉 confidence로는 탐지 불가능한 입력 크기 문제다.
- recognizer.py 수정 (공개 API 변경 없음, 전부 private):
  - `_clamp_size`: rec 입력 높이를 `_MAX_REC_HEIGHT=256`으로 상한 클램프
    (기존 longest side 2000 방어와 병행). enhance가 만든 초대형 입력도 여기서
    안전 범위로 내려온다.
  - `_find_line_segments`: 세로 잉크 프로파일(`_row_ink_profile`, Otsu 이진화 +
    소수 클래스 폴라리티 선택 + close 모폴로지 + 행별 합)로 라인 경계 검출.
    파라미터: 피크 대비 10% 행 잉크 임계값, 6px 갭 병합, 최소 라인 높이
    12px. 유효 세그먼트가 2개 미만이면 빈 리스트 반환(단일 라인 → 기존대로
    1회 호출, 성능 유지).
  - `_normalize_line`: 분할된 각 라인을 높이 128px로 정규화 후 rec 호출,
    위→아래 순서로 " ".join, score는 max.
- 실엔진 검증 결과:
  - 단일 라인 밴드(64x640): "두번째 자막" / "첫번째 자막" 정확.
  - 2줄 합성 이미지: "첫번째 라인 두번째 라인" 순서 보존, 각 라인 conf 0.9999.
  - pipeline CLI smoke(synth.mp4): "첫번째 자막"(0-3.667s), "두번째 자막"
    (4-6.667s) — 종전 "자막 째 번 두" 결함 해소.
- pytest 72 passed 유지. recognize mock은 `recognize` 상위에서 patch하므로
  영향 없음. `_find_line_segments`/`_predict`를 직접 stub하는 테스트를 새로
  추가할 때만 시그니처(y1,y2) 반쯤 열린 반개구간 아님 주의: 닫힌 구간
  [y1, y2]이다.
- preprocess.enhance의 `_TARGET_HEIGHT=720`은 이제 detector 입력용으로만
  적정하고 rec에는 recognizer가 클램프한다. enhance 자체 변경은 하지 않음
  (refactorer 참고).

## Det speedup (2026-08-25)

- 모델명 확인: paddlex 설정 디렉터리에 `PP-OCRv5_mobile_det.yaml`이 실존
  (`.venv/.../paddlex/configs/modules/text_detection/`). 추측 아님.
  `~/.paddlex/official_models/` 자동 다운로드로 정상 로드·추론 확인.
- config.py: `roi_band: tuple[float,float]|None = None` 추가(예: `(0.6, 1.0)`
  = 하단 40%). `for_mode`: fast=`PP-OCRv5_mobile_det`, auto/precise=
  `PP-OCRv5_server_det` 유지.
- detector.py: `detect`가 roi_band가 있으면 해당 밴드만 잘라 predict하고
  bbox y좌표에 y_offset을 더해 **원본 좌표계**로 반환. None이면 기존과 동일.
- 실측(/tmp/vte_det_bench.py, 합성 640x360 프레임 = 실제 파이프라인 det 입력,
  OMP_NUM_THREADS=8, 시스템 부하 load avg ~10 경합 하 1회 측정):

  | 조건 | 소요 ms | box 수 | 비고 |
  |---|---|---|---|
  | server det 전체 | 4865 | 1 | y=[303,335] |
  | mobile det 전체 | 513 | 1 | y=[300,340], **9.5배** |
  | server det + ROI(0.6,1.0) | 1975 | 1 | y=[300,336], 좌표 원본계 복원 확인 |
  | mobile det + ROI(0.6,1.0) | 404 | 1 | **12.0배** |

  ROI 박스 y좌표가 전체 검출 결과와 일치(±4px) → 좌표 복원 정상.
- 권장안: fast=mobile det(확정 적용), auto=presently server det 유지하되
  benchmarker가 실영상에서 mobile det 텍스트 누락률 검증 후 전환 판단,
  precise=server det(+자막 위치 고정 영상은 roi_band 옵션).
- 주의(성능): paddle CPU 스레드 수는 환경 변수 영향을 크게 받는다.
  벤치 스크립트 실행에서 `OMP_NUM_THREADS=8` 지정 시 server det이
  BENCHMARK 초회(9.9s/frame) 대비 절반 수준. 미지정 + 높은 시스템 부하
  (load avg 20+)에서는 단일 코어로 수 분 이상 걸리는 사례 확인(1080p 입력,
  18 CPU-min 초과 미완료). benchmarker 재측정 시 스레드 수와 부하 상태를
  기록할 것. 1080p 등 대형 입력은 det 내부 리사이즈 한도와 별개로 전처리
  비용이 지배적일 수 있음 — 파이프라인 입력은 원본 해상도 그대로임.

## Det downscale & small-text rec (2026-08-25)

### ① det_max_width (detector 입력 다운스케일)

- config.py: `det_max_width: int | None = 1280` 추가(None=원본 크기).
- detector.py: roi_band **밴드 크롭을 먼저** 하고 그 결과가 det_max_width보다
  넓으면 비율 유지 축소(cv2.INTER_AREA) 후 predict. 좌표 복원은 x/y 축별 배율
  (원본폭/축소폭)을 곱하고 y_offset을 나중에 더하는 순서라 밴드 오프셋이
  원본 좌표계에서 정확히 유지된다(밴드→축소 순서 채택: 이 순서는 y_offset이
  스케일과 무관하게 되므로 왜곡 없음 / 축소→밴드 순서는 밴드 비율 계산이
  축소된 프레임 기준이 되어 매번 환산이 필요해 실수 여지가 있음).
  min/max_box_height 필터도 복원된 원본 좌표 높이로 평가됨.
- for_mode 실측 기반 확정:
  - fast = mobile det + det_max_width=960
  - auto = server det + det_max_width=1280 (Config() 기본값과 동일)
  - precise = server det + det_max_width=**1280** (과제안의 None(원본)은
    기각 — server det @1920x1080은 미완료 30분+ 실측이므로 feasible 한계인
    1280으로 상한 고정)
- 실측(claude_first60s.mp4 t=5/15/25s 프레임 1920x1080, OMP_NUM_THREADS=8,
  시스템 부하 변동 있어 참고치):

  | 조건 | ms/frame (3프레임) | box 수 |
  |---|---|---|
  | mobile 원본(1920) | 13206 / 10919 / 11214 (~11.7s 평균) | 5/5/6 |
  | mobile + 1280 | 9671 / 4491 / 10119 (~7.4s) | 5/3/6 |
  | mobile + 960 | 7323 / 6330 / 7704 (~7.1s) | 5/2/6 |
  | server + 1280 | 49724 / 54427 / 93182 (~65s) | 6/3/4 |

  - mobile 원본 대비 960/1280 모두 약 1.6~2배. BENCHMARK의 ~20s/frame 관측과
    정합(부하 차).
  - server는 1080p 원본에서 30분+ 미완료였으나 **1280 축소 시 50~93s로
    회복** → 급격 저하의 원인은 det 전처리 리사이즈 한도와 대형 입력의
    상호작용으로 강하게 시사(원인 규명은 아님).
  - **주의(리콜)**: frame15에서 축소 시 box 수 감소(5→3→2, 소형 박스 소멸).
    다운스케일은 속도·리콜 트레이드오프. benchmarker 재측정 시 박스 수/
    누락 텍스트 비교 필요.

### ② 소형 텍스트 rec 최소 높이 보장

- recognizer.py: `_MIN_REC_HEIGHT = 48`. recognize 진입 시 crop 높이가
  48px 미만이면 INTER_CUBIC으로 48px까지 선형(단순 배율) 업스케일한 뒤 기존
  `_clamp_size → line split → rec` 적용. `_MAX_REC_HEIGHT=256` 클램프는
  그대로라 어순 파손 조건(288px+)에는 도달하지 않음 — 합성 자막
  "첫번째/두번째 자막" 실엔진 재확인 OK.
- enhance()와의 상호작용 — crop 단위 재확인이 필요한 이유:
  pipeline은 enhance(crop) 후 recognize를 호출하므로 대부분의 crop은 이미
  720 타깃으로 업스케일되어 들어온다. 그러나 enhance는
  `_MAX_UPSCALED_SIDE=2000`(긴 변 상한) 때문에 **가로로 긴 crop**(텍스트
  밴드, 전체폭 UI 라인)에서는 상한에 걸려 충분히 커지지 못한다. 예: 1900px
  폭 crop은 배율이 2000/1900≈1.05로 제한되어 h≈35px인 채 recognize에
  도착한다. 즉 enhance의 720 타깃은 "짧고 넓은" crop에 대해 무효화되며,
  recognizer에서 최종 게이트를 두어야 보장된다. 이것이 crop 단위 재확인 사유.
- 견본(실영상, mobile+1280 검출 box, enhance 경로 = pipeline 실제 경로):
  - side-cap 유효 case(in_h 43): th0(구버전) '몽 [0.67]' → th48
    '오늘 어떤 도움을 드릴까요? [0.95]'
  - raw(no enhance) 경로 추가 확인: '다 [0.68]'→'플러그인 [1.00]',
    '© < [0.41]'→'학습하기 [0.98]', 'B커넥터 [0.80]'→'커넥터 [0.95]'
  - pipeline 경로의 in_h≥48 case들은 전부 불변(회귀 없음).
- 임계값 근거: 32/48 스윕에서 32와 48 결과 동일 다수, 개선 사례들은
  in_h 41~44라 48이어야 트리거. 64는 개선 없음. 단, 미-enhance 33px
  single-line 1건은 업스케일 시 열화('오늘 어떤...'→'를릉몽록')가 관측되었으나
  pipeline 경로에서는 재현되지 않음(같 crop이라도 enhanced 입력에선 정상).
  48 유지.
- 역사적 결함 문자열 '그글에 클로드를 검색ㅎ D'는 전체해상도 det 지오메트리
  (downscale 전)에서 나온 것으로 t=30/36/42/48 + roi_band 조합 재현 불발.
  benchmarker 재측정에서 동일 구간 비교 요망.

## Rec line scaling & ASS export & Confidence score synthesis (2026-08-28)

- **ASS exporter 센티초 단위 정정**: `_ts_ass`의 `divmod` 상수 분모를 ms 기준(3,600,000 / 60,000)에서 cs 기준(360,000 / 6,000)으로 정정. 60초 이상 타임스탬프의 분 단위 계산 누락 문제 해결.
- **`max_side_limit 4000` 및 와이드 크롭 찌그러짐 해소**:
  - `_LINE_TARGET_HEIGHT`를 기존 128px에서 `korean_PP-OCRv5_mobile_rec` 최적 높이인 48px로 수정하여 aspect ratio 40:1 수준의 wide crop도 2000px 이내로 수용되도록 조정.
  - `_normalize_line`에 `new_w > _MAX_SIDE(2000)` 상한 클램핑 추가하여 PaddleOCR `max_side_limit of 4000` 경고 발생 차단.
  - `_clamp_size` 수행 시 `h >= 48`인 이미지의 높이가 폭 클램핑 과정에서 48px 미만으로 무너지는 현상을 막기 위해 최소 높이(48px) 보장 guard 적용.
- **Score 합성**: `best_text`가 투표율과 `track.scores`의 평균을 결합하여 `confidence = round(vote_ratio * avg_score, 4)` 형태로 실제 OCR 엔진 정확도를 출력에 반영.

