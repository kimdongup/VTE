/**
 * 앱 코어: 패널 레지스트리 + 전역 상태 + SSE 오케스트레이션.
 *
 * 모듈 확장 방법
 * --------------
 * 1. static/js/panels/ 아래에 패널 파일 하나를 만든다.
 *    패널은 `{ name, mount(ctx) }` 를 기본 내보낸다.
 * 2. 이 파일에 import 한 줄 + App.register(...) 한 줄을 추가한다.
 * 그 외 코어는 건드리지 않아도 된다.
 */

import { api } from "./core/api.js";
import { App, toast } from "./core/registry.js";

// ---- 패널 등록 (새 기능이면 여기만 수정) ----
import controls from "./panels/controls.js";
import preview from "./panels/preview.js";
import transcript from "./panels/transcript.js";
import exporter from "./panels/exporter.js";

App.register(controls);
App.register(preview);
App.register(transcript);
App.register(exporter);

// ---- 전역 상태 (모든 패널이 이 객체를 공유) ----
const state = {
  video: null,
  mode: "auto",
  job: null,        // latest JobSnapshot
  events: [],       // 완료된 이벤트
  progress: null,   // 최신 ProgressUpdate
};
App.state = state;

// ---- 상태 헬퍼 ----
const $status = document.getElementById("status-pill");
function setStatus(label, stateName) {
  $status.dataset.state = stateName;
  $status.querySelector(".label").textContent = label;
}

// ---- SSE 핸들링 ----
let closeSub = null;

function connect() {
  if (closeSub) closeSub();
  closeSub = api.subscribe({
    snapshot(msg) {
      state.job = msg.job;
      if (msg.job && msg.job.state === "running") {
        setStatus("추출 중", "running");
        state.video = msg.job.video;
        state.mode = msg.job.mode;
        if (msg.job.progress) {
          state.progress = msg.job.progress;
          App.emit("progress", msg.job.progress);
        }
      } else if (msg.job && msg.job.state === "done") {
        state.events = msg.job.events || [];
        setStatus("완료", "done");
        App.emit("done", state.events);
      } else if (msg.job && msg.job.state === "error") {
        setStatus("오류", "error");
        toast(msg.job.error || "알 수 없는 오류");
        App.emit("error", msg.job.error);
      }
      App.emit("job", state.job);
    },
    progress(msg) {
      state.progress = msg;
      App.emit("progress", msg);
    },
    done(msg) {
      state.events = msg.events || [];
      setStatus("완료", "done");
      App.emit("done", state.events);
    },
    error(msg) {
      setStatus("오류", "error");
      toast(msg.message || "추출 실패");
      App.emit("error", msg.message);
    },
    ping() { /* keep-alive */ },
  });
}

// ---- 공통 명령 API (패널이 호출) ----
App.commands = {
  async start(video, mode, overrides, start, end) {
    if (!video) {
      toast("영상 경로를 입력하세요");
      return false;
    }
    state.video = video;
    state.mode = mode;
    state.events = [];
    state.progress = null;
    setStatus("추출 중", "running");
    App.emit("reset");
    try {
      const { job } = await api.startExtract({ video, mode, overrides, start, end });
      state.job = job;
      App.emit("job", job);
      return true;
    } catch (err) {
      setStatus("대기 중", "idle");
      toast(err.message);
      return false;
    }
  },
  async cancel() {
    try {
      await api.cancel();
      toast("취소 요청됨");
    } catch (err) {
      toast(err.message);
    }
  },
  seek(ts) {
    App.emit("seek", ts);
  },
};

// ---- 시작 ----
connect();
App.boot();
toast("VTE UI 준비 완료");
