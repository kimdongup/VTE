# BENCHMARK — 합성 영상 (12초) 실측 결과

- 측정일: 2026-08-25
- 측정자: benchmarker 에이전트
- 영상: `tests/fixtures/make_synth_video.py`의 `make_synth`로 생성한
  640x360 / 3fps / 12.000초 mp4 (mp4v). 정답: "첫번째 자막"(0~3s),
  "두번째 자막"(4~7s), 8~12s 자막 없음.
- 실행 순서: fast → auto → precise, 각 1회, 워밍업 없음. 첫 실행(fast)에
  PaddleOCR 모델 초기화(지연 로딩)가 포함됨. 단, 모델은 생성자에서 즉시
  로드되지 않고 첫 추론 시 로드되므로 사실상 각 모드 run_extract 내 첫
  detect 호출에서 로드 비용이 발생한다(아래 병목 참조).

> 각주: 동시 작업 중 측정(다른 에이전트가 같은 .venv와 엔진 파일 공유), 변동 가능.

## 환경

| 항목 | 값 |
|---|---|
| OS | macOS 15.7.9 (Build 24G830) |
| CPU | Intel(R) Core(TM) i9-9880H @ 2.30GHz |
| RAM | 17179869184 bytes = 16 GiB |
| Python | 3.11.11 (.venv) |
| OCR | PaddleOCR 3.x, det=PP-OCRv5_server_det, rec=korean_PP-OCRv5_mobile_rec, CPU |

## 결과 표

`Config.for_mode("auto")`는 기본 `Config()`와 동일함을 `src/vte/config.py:31`
에서 확인 (auto 분기가 `return cls()`).

| mode | total(s) | events | texts | duration 대비 배율 |
|---|---|---|---|---|
| fast (2fps) | 132.95 | 2 | "첫번째 자막", "자막 째 번 두" | ×11.1 |
| auto (=기본, 3fps) | 153.74 | 2 | "첫번째 자막", "자막 째 번 두" | ×12.8 |
| precise (6fps) | 146.09 | 2 | "첫번째 자막", "자막 째 번 두" | ×12.2 |

이벤트 타임라인 세부 (start~end):

| mode | 이벤트 1 | 이벤트 2 |
|---|---|---|
| fast | 첫번째 자막 0.00~3.50 (conf 1.0) | 자막 째 번 두 4.00~6.67 (conf 1.0) |
| auto | 첫번째 자막 0.00~3.67 (conf 1.0) | 자막 째 번 두 4.00~6.67 (conf 1.0) |
| precise | 첫번째 자막 0.00~3.83 (conf 1.0) | 자막 째 번 두 4.00~6.67 (conf 1.0) |

confidence는 segmenter의 투표 비율(min(n, vote_frames))이며 개별 OCR score가
아님에 유의.

## 정확도 견본

- 정답: "첫번째 자막"(0~3s), "두번째 자막"(4~7s).
- 이벤트 1: 3개 모드 모두 텍스트 일치, 시작/종료 시각 근접 (오차 ≤ 0.83s,
  precise가 가장 긴 end — 샘플 간격이 촘촘해 트랙 유지가 길어진 것으로 보임).
- 이벤트 2: **3개 모드 모두 오인식** — "두번째 자막"이 "자막 째 번 두"로
  출력됨. 글자 순서가 뒤섞인 형태. 결함 보고로 coder 확인 필요 (본 문서는
  측정만 수행, 원인 단정 없음).
- 8~12초 무자막 구간에서 오탐 이벤트 없음.

## 병목 분해 (별도 측정)

모델 로드 vs 프레임 처리 분해를 위해 생성자/첫 추론/안정 추론을 따로 측정:

| 구간 | 시간 |
|---|---|
| TextDetector+Recognizer 생성자 | 0.000s (완전 지연 초기화) |
| 첫 detect 호출 (모델 로드 포함) | 8.906s |
| 첫 recognize 호출 (모델 로드 포함) | 1.850s |
| detect 안정 상태 평균 (5회) | 9.856s/호출 |
| recognize 안정 상태 평균 (5회) | 1.230s/호출 |

> 위 항목도 동시 작업 중 측정, 변동 가능.

관찰:
- 모델 로드(첫 추론 내 ~10s)보다 **프레임당 detection 비용(~9.9s)** 이
  지배적. server_det 모델이 CPU에서 무거우며, 전체 시간의 절대 다수가
  detection에 소비된 것으로 추정.
- fast/auto/precise 총시간 차이(133~154s)는 sample_fps 배수보다 작음 —
  scene detector가 정적 프레임을 건너뛰고(`extend_static`) 크롭 변경이 없으면
  재인식을 생략하기 때문(pipeline.py `_CROP_CHANGE_THRESHOLD`).

## 개선 제안 (coder/refactorer용)

1. det 모델을 mobile 계열로 낮추거나, 하단 밴드 등 관심 영역 crop 후 detect를
   제한하면 프레임당 detection 비용을 크게 줄일 수 있을 것으로 보임(실측 전제).
2. "두번째 자막" 오인식은 recognizer 입력 전처리(enhance/upscale) 또는
   텍스트 라인 방향(orientation) 모델 영향 가능성 — 결함 재현 후 수정 요망.
3. confidence가 투표 비율이라 항상 1.0에 수렴함 — 개별 OCR score 노출 여부를
   exporter 설계와 함께 검토 가치 있음.

## 산출물 위치

- 측정 스크립트/결과 JSON: 저장소 밖
  `/var/folders/1q/pw0bpnyd5hn51b6jgtbfrkqw0000gn/T/opencode/vte-bench/`
  (`bench.py`, `bench_load.py`, `results.json`, `synth.mp4`)

## Real video first-minute (2026-08-25)

- 측정일/측정자: 2026-08-25, benchmarker 에이전트
- 영상: `/Users/mac/Downloads/my_training/YTDown.com_claude_1080p.mp4`
  (1920x1080, 30fps, 전체 길이 약 4239초 ≈ 70.7분, 189MB)
- 범위: **첫 60초만** (`run_extract(video, cfg, start=0.0, end=60.0)`),
  각 설정 1회 실행. 모델 로드는 첫 detect 호출에 포함됨(워밍업 없음).
- 환경 변수: `OMP_NUM_THREADS=8` (coder 지시).

### 환경

| 항목 | 값 |
|---|---|
| OS | macOS 15.7.9 |
| CPU | Intel(R) Core(TM) i9-9880H @ 2.30GHz (8코어/16스레드) |
| RAM | 16 GiB |
| Python | 3.11.11 (.venv) |
| OCR | PaddleOCR CPU, rec=korean_PP-OCRv5_mobile_rec 고정 |

### 결과 표

| 설정 | det 모델 | fps | ROI | time(s) | 배율 | detect호출 | events |
|---|---|---|---|---|---|---|---|
| A fast | PP-OCRv5_mobile_det | 2.0 | 없음 | 322.7 | ×5.38 | 10 | 19 |
| B fast+roi | PP-OCRv5_mobile_det | 2.0 | (0.6,1.0) | 158.6 | ×2.64 | 9 | 5 |
| C auto | PP-OCRv5_server_det | 3.0 | 없음 | 미측정 | — | — | — |

C 미측정 사유: 단일 프레임(1080p)에 대한 server_det `detect` 호출이
완료되지 않음을 2회 확인. 프로브(t=35초 프레임, 모델은 이미 캐시됨)에서
첫 호출이 900초 타임아웃 내 미완료, 재시도(타임아웃 1800초)에서도
call#1 로그가 찍히지 않은 채 종료. 프레임당 비용이 최소 30분 수준이므로
60초 구간 전체(detect 호출 수십 회)는 현실적으로 실행 불가하여 기록하지
않음. 합성영상(640x360) 때의 server_det 안정 추론 ~9.9s/프레임과 대비되는
급격한 저하(1080p 입력에서 발생) — coder 확인 필요.

### 이벤트 견본 (A / B)

영상 내용: claude.ai 웹 UI 화면 녹화로 추정되는 영상. 자막 형태의 텍스트가
아니라 화면 곳곳의 한국어 UI 텍스트(버튼/안내문/입력창 등)가 검출 대상이 됨.

A(fast) 19개 중 일부:

- 12.5~33.5 `'대 Y은융Y -'`
- 34.0~52.5 `'어떤 도움을 드릴까요? 오늘'`
- 34.0~52.5 `'작성하기'` / `'학습하기 S'` / `'</>코드'`
- 34.5~52.5 `'구글에 클로드를 검색해'`
- 53.0~59.5 `'프로젝트 지침 설정'`
- 53.0~59.5 `'복잡한 문제는 단계별로 생각하고 추론 과정을 보여드립니다.구체적인 예시를 사용합니다.'`
- 54.5~59.5 `'글쓰기나 블로그 – I 4'`

B(fast+roi) 5개 전체:

- 12.0~33.5 `'사용하시면'`
- 34.0~52.5 `'그글에 클로드를 검색ㅎ D'`
- 53.0~53.5 `'취소'`
- 53.0~59.5 `'지침 저장'`
- 54.5~59.5 `'기나 S - I ㄷ'`

### 자막 판정

- **한글 "자막" 영상이 아님.** 화면 녹화형 UI 텍스트가 다수 검출됨.
  한글 텍스트 자체는 존재하며 검출·인식됨(예: "어떤 도움을 드릴까요?",
  "구글에 클로드를 검색해"). 따라서 "텍스트 부재" 판정 절차(프레임 5장 저장
  후 직접 detect)는 불필요하여 수행하지 않음.
- 다만 인식 품질 문제가 뚜렷함: A/B 모두 글자 일부 유실·왜곡
  (예: '그글에 클로드를 검색ㅎ D', 'O단면밀영불영능분품정',
  '기나 S - I ㄷ'). UI 작은 글꼴/고밀도 레이아웃이 자막 전용 전처리와 맞지
  않는 것으로 보이나 원인 단정은 하지 않음(측정 에이전트 범위 밖).

### A/B/C 비교 결론

1. **roi_band=(0.6,1.0) 유효**: 동일 fast 모드에서 322.7s → 158.6s
   (**약 2.0배 향상**, 배율 ×5.38 → ×2.64). detect 호출 수는 비슷(10 vs 9)하므로
   개선은 프레임당 detection 비용 감소(입력 픽셀 40%)에서 온 것.
   부작용으로 화면 상단 60%의 텍스트는 의도대로 제외됨(19개→5개 이벤트).
2. **mobile det도 1080p에서 무겁다**: 안정 상태 약 20s/프레임 로그 관측
   (A: #10까지 평균 20.7s/프레임). 합성영상 640x360 때보다 크게 증가.
   실사용(70분 영상)에는 여전히 부족.
3. **server det(auto)는 1080p에서 사실상 사용 불가** (위 미측정 사유 참조).

### coder에게

1. **server det 1080p 급격 저하**: 640x360에서 ~9.9s/프레임이던
   PP-OCRv5_server_det이 1920x1080 입력에서 단일 프레임 30분+
   (미완료). PaddleOCR det 전처리 리사이즈 정책과 결합한 문제로 추정되나
   원인은 미규명. **프레임 다운스케일 후 detect**(예: 긴 변 ≤1280) 옵션
   검토 요망 — mobile det에도 적용 시 추가 수 배 개선 여지.
2. **실영상 인식 품질**: 위 견본과 같이 글자 유실/왜곡 다수.
   enhance/upscale 파이프라인이 자막(큰 글씨) 가정으로 되어 있어 UI 소형
   텍스트에서 열화하는 가능성. 재현 데이터:
   `/var/folders/.../opencode/vte-bench3/A_fast.json`, `B_fast_roi.json`.
3. confidence 전부 1.0 (투표 비율 한계, 기존 TODO 항목과 동일).
4. 본 측정 스크립트 1차 실행은 벤치마커 쪽 버그(TextEvent 필드명)로
   크래시 후 재실행한 것이며 VTE 코드 결함 아님.

측정 산출물: `/var/folders/1q/pw0bpnyd5hn51b6jgtbfrkqw0000gn/T/opencode/vte-bench3/`
(`bench_one.py`, `probe_auto.py`, `A_fast.{log,json}`, `B_fast_roi.{log,json}`,
`probe_auto.log`)

## Re-measure after downscale (2026-08-25)

- 측정일/측정자: 2026-08-25, benchmarker 에이전트
- 영상: `claude_first60s.mp4` (저장소 루트)
  (1920x1080, 60초 클립만 사용)
- 대상: coder가 반영한 `Config.for_mode("fast")` = mobile det +
  `det_max_side=960`. 기준선은 위 "Real video first-minute" 섹션의
  A(원본 폭) / B(fast+roi).
- 범위: `run_extract(video, cfg, start=0.0, end=60.0)`, 각 설정 1회.
- 환경 변수: `OMP_NUM_THREADS=8`.
- 부하(load avg): A' 시작 시 3.46/4.27/5.91, 종료 시 5.86/4.88/5.87,
  B' 종료 시 4.19/4.56/5.69. 다른 에이전트와 동시 작업 중이라 변동 가능.

### 환경

| 항목 | 값 |
|---|---|
| OS | macOS 15.7.9 |
| CPU | Intel(R) Core(TM) i9-9880H @ 2.30GHz (8코어/16스레드) |
| Python | 3.11.11 (.venv) |
| OCR | PaddleOCR CPU, det=PP-OCRv5_mobile_det + det_max_side=960, rec=korean_PP-OCRv5_mobile_rec |

### 결과 표

| 설정 | ROI | time(s) | 배율 | detect호출 | events | 기준선 | 개선율 |
|---|---|---|---|---|---|---|---|
| A' fast(mobile+960) | 없음 | **158.2** | **×2.64** | 10 | 20 | A: 322.7s ×5.38 | **2.04배 빠름 (−50.9%)** |
| B' fast+roi+960 | (0.6,1.0) | **38.2** | **×0.64** | 8 | 5 | B: 158.6s ×2.64 | **4.15배 빠름 (−75.9%)** |

- A'는 60초 클립 처리에 158.2초(실시간의 2.64배). B'는 최초로 클립 길이보다
  빠름(×0.64, 실시간 대비 1.56배 빠름).
- detect 호출당 비용도 감소: A' 평균 약 13.9→15.8s/frame 로그 관측
  (기준선 A는 약 20.7s/frame). 프레임당 절감 + 일부 호출 생략 효과.
- B' events=5는 기준선 B와 동일 개수이나 텍스트 품질 견본:
  `'사용하시면 I −'`, `'|0른 를크 은Y i I −'`, `'|소 지'`, `'|'`,
  `'지침 저 -'` — roi 밴드 크롭 후 960 축소가 겹치며 인식 열화 심화
  (기준선 B 때보다 오히려 나빠짐).

### 리콜 관찰 (t≈15s, coder 보고 "프레임15 축소 시 소형 box 소멸 5→2" 검증)

단일 프레임(t=15.0s, 1920x1080)을 원본 폭 / 1280 / 960으로 직접 detect:

| 입력 폭 | boxes | detect 시간 | 비고 |
|---|---|---|---|
| 1920 (원본) | 5 | 10.3s | 좌상단 로고류(h≈118), 중앙 UI 3개(h=52~83), 하단 자막(h=102) |
| 1280 | 3 | 3.8s | 하단 자막 보존, 중앙 UI 소실, h≈10 잡박스 2개 신규 |
| 960 | 2 | 2.7s | 하단 자막(h=76) + 우상단 박스 1개, 중앙 UI 3개 소실 |

- **coder 보고 재현 확인**: 960 축소에서 중앙 UI 소형 텍스트(box 3개,
  h=52~83)가 사라져 5→2. 추가로 960에서 원본에 없던 우상단 박스 1개가
  새로 검출됨(오탐 가능성).
- 파이프라인 최종 출력 기준으로는: A'의 t≈15s 이벤트는
  `'사용하시면 모'(12.0~33.5)` 1개로, 골든(tests/golden/first60s.json,
  20개)과 **20개 이벤트 전부 텍스트·시각 완전 일치** — 소실된 소형 UI
  텍스트는 트래킹/투표 단계에서 이미 걸러지던 것들이어서 골든 대비
  리콜 손실 없음.
- 단 주의: **골든 자체도 det_max_side=960으로 캡처되어 있어**(meta 참조)
  "원본 폭 대비 리콜"은 위 프레임 프로브로만 판단 가능. 즉 960 축소는
  화면 중앙부 소형 UI 텍스트를 포착하지 못하며, 자막(하단 대형 텍스트)
  용도로는 안전.

### 권장안 (fast/auto 프리셋 최종 판단 제안)

1. **fast = 현재 구조(mobile + 960) 유지 적합**: 기준선 대비 2배 향상,
   골든 무손실. 자막 추출 주 용도 기준 리콜 문제 없음.
2. **auto에도 det_max_side 상한 필수**: server det은 원본 1080p에서
   미완료(30분+, 전 섹션)였으므로 auto/precise가 1280 상한을 쓰는 현행
   config가 정상 동작의 전제. 원본 폭 경로는 남겨두지 않을 것.
3. **roi+960 조합(B')은 속도 대비 품질 손실 커서 프리셋 후보 부적합**:
   ×0.64로 실시간보다 빠르지만 텍스트가 `'지침 저 -'` 수준으로 붕괴.
   roi를 쓰려면 crop 후에도 축소를 1280 이상으로 유지하거나 rec 입력
   업스케일 보정이 필요 — coder 검토 요망.
4. 중앙 UI 소형 텍스트까지 필요한 사용자라면 precise(1280) 사용 안내
   권장. fast는 "하단 자막 특화 프리셋"으로 문서화하는 것이 정직함.

측정 산출물: `/var/folders/1q/pw0bpnyd5hn51b6jgtbfrkqw0000gn/T/opencode/vte-bench4/`
(`bench_one.py`, `probe_frame15.py`, `A_fast_960.{log,json}`,
`B_fast_roi_960.{log,json}`, `probe_frame15.json`)
