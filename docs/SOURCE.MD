# SOURCE.MD — 유사 구현 프로젝트 조사 및 특징 검토

조사일: 2026-08-25 · 대상: 영상 하드서브(자막) 타임구간 검출 + 한국어 텍스트 추출

## 1. 주요 유사 프로젝트

### 1.1 YaoFANGUK/video-subtitle-extractor (VSE) ★9.2k
https://github.com/YaoFANGUK/video-subtitle-extractor (Apache-2.0)
본 설계와 **가장 유사한 완성형**. 본 설계의 파이프라인(자동 영역검출 → 인식 → 중복제거 → SRT)을 그대로 구현.

**특징**
- 딥러닝(DBNet 계열) 텍스트 검출로 **자막 영역 자동 검출** — 수동 ROI 불필요 (본 설계와 동일 방향)
- 비(非)자막 영역 텍스트 필터링, 워터마크·방송국 로고 제거 기능 내장
- 중복 자막 라인 제거 후 SRT/TXT 생성
- 87개 언어 지원(한국어 포함), GUI + CLI, 배치 처리
- 실행 모드 3종: **Fast**(경량 모델, 빠름/누락 가능) / **Auto**(GPU면 대형 모델) / **Precise**(전 프레임 정밀, 매우 느림)
- CUDA / CPU / DirectML / ONNX 4가지 런타임 백엔드

**교훈/시사점**: Precise 모드가 45분 영상에 수 시간 걸린다는 사용자 보고(GitHub Discussions #435) → 속도·정확도 모드 분리 필요. "같은 텍스트 연속 라인 무조건 병합"이 오히려 불편하다는 피드백 → 병합 옵션화 필요.

### 1.2 timminator/VideOCR ★736
https://github.com/timminator/VideOCR (MIT, GUI+CLI)
PaddleOCR 로컬 처리 + Google Lens 하이브리드(클라우드 인식) 지원. **본 설계의 Recognizer 추상화 방향과 일치**하는 실례.

**특징 (아키텍처 참고 가치 최상)**
- **장면 전환(scene-change) 검출로 정적 프레임 스킵** — 중복 처리 절감
- **Temporal smoothing**: 5~15프레임 윈도우에서 중복 검출 융합 → 깜빡임 제거, debounce(0.5~5s)로 일시적 노이즈 필터
- 신뢰도 임계값(기본 >90%) 필터링
- 전처리: 자동 명암 보정, 노이즈 제거, **SD 저해상도 업스케일**, 디인터레이싱
- ROI 크롭으로 처리량 30~70% 절감
- 스크롤 티커(수직/수평 이동 텍스트) 추적 기능
- 출력: SRT/TXT/JSON(bbox+confidence)/ASS

### 1.3 SWHL/RapidVideOCR ★509
https://github.com/SWHL/RapidVideOCR (Apache-2.0)
- **VideoSubFinder**(키 프레임 추출 도구)와 결합: 자막이 바뀐 프레임만 먼저 골라내고 → RapidOCR로 인식 → SRT/ASS/TXT
- pip 설치형 경량 파이프라인. "변화 프레임만 OCR"이라는 2단계 구조가 본 설계의 Segmenter 아이디어와 같음

### 1.4 참조 프로젝트 (사용자 지정)
| 프로젝트 | 특징 | 한계 |
|---|---|---|
| wyb330/MakehardSub | 프레임 차이로 타임코드 추출 → Tesseract OCR 2단계 | 자막 위치 수동 지정(--pos) 필수 |
| JiHaeK/videoTotext | OpenCV 6단계 전처리 + CNN 글자판별 + Tesseract | Tesseract 한글 인식률 낮음, 자체 학습 모델 필요 |

### 1.5 국내 사례
- **jiwoo-jus/getScript**: 드래그로 자막 영역 수동 설정 → 추출 + TTS 변환 + 번역까지 확장. 수동 ROI 방식의 UX 사례.
- **블로그 구현(reddol18)**: EasyOCR(ko,en) + 0.5초 간격 샘플링 + **텍스트 diff 기반 구간 분리 + 구간 내 다수결(majority vote)로 최종 텍스트 선택** → 본 설계 M3에 반영할 만한 검증된 저비용 기법.

### 1.6 상용/신기술 참고
- **Google Cloud Video Intelligence TEXT_DETECTION**: 텍스트별 `{text, segments[{start,end,confidence}]}` 구조 — 이벤트 단위 출력 스키마의 업계 표준 예시.
- **SubHero 등 VLM(Ollama qwen3.5-vl 등) 기반 추출기**: 2026년 트렌드 — OCR 전문 모델 대신 시각 LLM이 화면 텍스트를 맥락과 함께 읽는 방식. 간섭 많은 화면(PPT·UI 겹침)에서 강점. 엔진 교체 가능 구조의 근거.

## 2. 종합 검토 — 본 설계 대비 발견한 것

| 항목 | 본 설계(DESIGN.md) | 유사 프로젝트 관행 | 판단 |
|---|---|---|---|
| 검출 엔진 | PaddleOCR det | 동일(VSE/VideOCR) | 유지 |
| 한글 인식 | PaddleOCR rec(ko) | PP-OCRv5 korean 모델(정확도 88~90%, v3 대비 +30%p) | **v5 명시 필요** |
| 프레임 선택 | 최선명 프레임 1개 | 다수결 투표 + 선명도 혼합 | 보완 |
| 깜빡임 처리 | gap 메우기 0.3s | debounce 0.5s + 프레임윈도우 융합 | 임계값 재조정 |
| 장면전환 스킵 | 없음 | 정적 프레임 스킵으로 대폭 절감 | **신규 추가** |
| 전처리 | 없음 | 명암보정·업스케일·디인터레이스 | 신규 추가 |
| 워터마크/로고 | min_duration으로 부분 대응 | 전체 영상에서 정적인 bbox = 로고로 필터 | 신규 추가 |
| 추적 | IoU 그리디 | SORT(Kalman+헝가리안) | 업그레이드 경로 추가 |
| 진행률/재개 | 없음 | 진행률 표시, 구간 trim, 배치 | 신규 추가 |
