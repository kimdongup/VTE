# REFACTOR_NOTES

refactorer 에이전트의 리팩터링 누적 기록.

## 2026-08-25 (M(n-2) 창, 48 테스트 기준)

### 완료 요약
- `tracker.py`:
  - `update`를 매칭(IoU → 중심거리 폴백) → 신규 트랙 생성(`_spawn`) → 미스 카운팅(`_age_unmatched`) 단계로 분리.
    매칭 로직을 `_best_iou_match`, `_nearest_center_match`, EMA 스무딩을 `_smoothed`로 추출.
  - missed 만료 트랙 제거를 인덱스 팝(`_finish`) 대신 id 집합 + `_partition` 방식으로 변경.
    기존 코드는 한 프레임에서 2개 이상 트랙이 동시 만료되면 pop에 의한 인덱스 시프트로
    엉뚱한 트랙이 종료될 수 있는 잠재 결함이 있었음(단일 만료 시 동작 동일).
  - 죽은 코드가 된 `_finish` 제거.
- `segmenter.py`:
  - `build_events`에서 track→event 변환을 `_track_to_event`(20줄)로 분리. build_events 본체는 파이프라인 나열만 남김.
  - `_fill_gaps`의 하드코딩 유사도 임계값 85 → `cfg.sim_threshold` 전달(기본값 85로 동작 동일).
  - `best_text` 내 매직넘버 80을 모듈 상수 `_VOTE_MATCH_RATIO`로 명명(config에 해당 값 없음).
- `exporter.py`: 공개 함수(`to_srt/to_txt/to_json/to_ass/export`)에 `list[TextEvent]` 타입 힌트 추가.
- `filters.py`: `models` 임포트 두 줄을 한 줄로 정리.

### 최종 pytest 결과
- 48 passed (변경 각각 직후 재실행, 항상 녹색 유지).

### coder에게 제안 (소유권 규칙상 미수정)
- `postprocess.py`는 소유권에 포함되어 있으나 수정 필요 없음(이미 간결함).
- 소유권 외 파일에서 발견한 사항:
  - `pipeline.py`: 프레임 루프 내 로직이 길어 함수 분리 여지 있음(coder 창에서 검토 권장).
  - `config.py`: `Config.for_mode("precise")`가 `debounce_gap=0.4` 등 일부 값만 조정 —
    모드별 오버라이드가 늘어나면 `dataclasses.replace` 패턴으로 통일하면 가독성 향상.

## 2026-08-25 refactorer 창 — `pipeline.py` 분리

- 소유 파일: `src/vte/pipeline.py` (단일 파일, 순수 리팩터링)
- 시작/종료 모두 `pytest tests/ -v` 72 passed 녹색 유지.

### 구조 변경
- `RecognitionCoordinator` 클래스 신설: 활성 트랙 재인식 + 시그니처 비교
  + split 인계를 캡슐화. 내부에 `_states: dict[int, _RecState]`와
  `sample_interval`, tracker 참조 보유.
  - `process_frame()`: 샘플 1개 처리(스냅숏 루프 유지 — split으로 추가된
    successor는 당장 재처리하지 않는 기존 동작 보존).
  - `_process_track()`: crop → 크기 가드 → 서명 diff → OCR → 한글 필터 →
    split 판정 → 확정.
  - `_hand_over()`: 트랙 종료 + `tracker.split()` + successor 상태 초기화.
- `_RecState.update()` 헬퍼 추가로 sig/confirmed/score 3중 대입 중복 제거.
- `run_extract`는 "샘플 순회 → coordinator 위임 → finish → segmenter 흐름"의
  얇은 조율자로 축소 (scene skip / extend_static 로직만 최상위에 유지).
- 타입 힌트 정비: `TextBox`, `Track`, `Iterable[Track]` 명시.

### cvt_gray/gray_crop 관련
- 작업 지시에 있던 `cvt_gray`/`gray_crop` 모듈 수준 헬퍼는 현재 pipeline.py에
  존재하지 않았음(이전 리팩터에서 제거된 것으로 추정). 대신 남아있던
  `_thumb`(BGR→GRAY+resize)과 preprocess.sharpness 계열의 역할만 주석으로
  구분. preprocess.py는 coder 소유라 건드리지 않음.

### benchmarker 메모
- 알고리즘·호출 횟수 불변: 정적 프레임 여부 판정 전 OCR 스킵 구조 그대로.
- 미세 차이: `_RecState`가 `__slots__` 유지 + `update()` 메서드 호출 추가로
  속성 대입 3회가 메서드 콜 1회+대입 3회가 되었으나 측정 가능한 수준 아님.

## 2026-08-25 refactorer 창 — 인계 책임 정리 (close_track / Track.starting)

- 소유 파일: `src/vte/models.py`, `src/vte/tracker.py`, `src/vte/pipeline.py`
- 시작 시 72 passed 녹색 확인. 종료 시 83 passed(창 중간에 tester의
  split/extend_static 단위테스트 추가분 포함) 녹색 유지.
- 공개 API 호환: `update/split/extend_static/finish_all`, `run_extract`
  시그니처 불변. `split`에 키워드 전용 `end_ts=None` 추가(기존 호출 무영향).

### 구조 변경
- `models.Track.starting(id, frame_idx, ts, box)` 클래스메서드 신설:
  신규 트랙 초기화(id/첫 box/start_ts=end_ts=ts)를 한 곳으로. `_spawn`과
  `split`이 동일 팩토리를 쓰게 되어 split successor 초기화 필드 나열 제거.
  models.py에 모듈 docstring + TextBox/Track/TextEvent 역할 경계 문서화.
- `RegionTracker.close_track(track_or_id, end_ts=None)` 신설: 활성 트랙 1개를
  조기 종료하는 유일한 경로. `end_ts` 지정 시 트랙 내부에서 클램프.
  Track 객체 또는 id 모두 받음. 이로써 tracker 외부에서
  `track.end_ts = ...` 직접 대입하는 코드는 pipeline에서 소멸.
- `split`을 `close_track` + `_spawn` 조합으로 재구성. 시맨틱 불변:
  - 반환값(Track | None) 동일, 미스 상태 해제 동일.
  - successor가 predecessor의 슬롯 인덱스를 계속 차지
    (`insert(idx, pop())`) — 기존 `tracks[i] = successor`와 순서 동일.
  - `end_ts` 미지정 시 기존처럼 종료 트랙의 end_ts를 건드리지 않음.
- `pipeline._hand_over`: `track.end_ts = boundary` 직접 대입 + `split` 2단계를
  `split(..., end_ts=boundary)` 1회 호출로. boundary 계산(스왑 시점 클램프)
  근거를 docstring에 데이터 흐름 3단계로 명시.
- `_RecState.with_reading()` 클래스메서드 추가 — hand_over 시 successor 상태
  시딩(`nxt = _RecState(); nxt.update(...)`) 2줄을 1줄 선언으로.
- `RecognitionCoordinator` docstring에 tracker(coordinator) 책임 분리 명시:
  tracker=생명주기(spawn/extend/close), coordinator=내용(texts/_states).
- `tracker._partition` 콜백에 `Callable[[Track], bool]` 타입 힌트.

### 동작 불변 확인
- split/extend_static 시맨틱(반환값·종료 처리) 유지 — tester가 창 도중 추가한
  해당 단위테스트들 포함 전체 통과.
- OCR 호출 횟수·매칭 알고리즘 불변(benchmarker 재측정 불필요).

### coder에게 제안
- `Config`에 sample_interval 관련 값이 `RecognitionCoordinator._sample_interval`
  로만 존재 — 추후 `cfg` 파생 프로퍼티로 옮기면 coordinator가 cfg 의존 축소.
- `close_track` 도입으로 향후 scene-cut 강제 종료 등 "조기 종료" 요구가 생기면
  반드시 이 API를 통해야 함(외부 end_ts 직접 대입 금지 관례).
