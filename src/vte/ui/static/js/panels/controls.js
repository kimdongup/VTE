/**
 * 제어 패널: 영상 경로, 실행 모드, 시작/취소 버튼.
 * 사이드바 상단에 mount된다.
 */

import { toast } from "../core/registry.js";

const MODES = [
  { id: "fast", label: "빠름", hint: "2fps · mobile det" },
  { id: "auto", label: "자동", hint: "3fps · server det" },
  { id: "precise", label: "정밀", hint: "6fps · 고신뢰" },
];

export default {
  name: "controls",
  mountPoint: "sidebar",

  mount(el, App) {
    el.innerHTML = `
      <div class="side-card">
        <h3>추출 설정</h3>
        <div class="field">
          <label for="ctrl-video">영상 경로</label>
          <div class="file-row">
            <input id="ctrl-video" class="input" placeholder="/path/to/video.mp4" />
            <button id="ctrl-pick" class="btn btn--sm" type="button">찾기</button>
          </div>
        </div>
        <input id="ctrl-file" type="file" accept="video/*" hidden />
        <div class="field">
          <label>실행 모드</label>
          <div class="mode-chips" id="ctrl-modes">
            ${MODES.map((m) => `
              <button class="chip" data-mode="${m.id}" aria-pressed="${m.id === "auto"}" type="button">
                ${m.label}<small>${m.hint}</small>
              </button>`).join("")}
          </div>
        </div>
        <div style="display:flex;gap:8px;margin-top:14px">
          <button id="ctrl-start" class="btn btn--primary" style="flex:1" type="button">추출 시작</button>
          <button id="ctrl-cancel" class="btn btn--danger" type="button" disabled>취소</button>
        </div>
      </div>
    `;

    const $video = el.querySelector("#ctrl-video");
    const $file = el.querySelector("#ctrl-file");
    const $start = el.querySelector("#ctrl-start");
    const $cancel = el.querySelector("#ctrl-cancel");
    const $modes = el.querySelector("#ctrl-modes");

    let mode = "auto";

    // 파일 선택은 브라우저가 읽을 수 없으므로 데스크톱 경로를 입력받아
    // 서버(로컬)가 참조한다. "찾기"는 데스크톱 파일 선택 다이얼로그를 띄우고
    // 이름만 보여준 뒤, 사용자가 실제 경로를 입력하도록 안내한다.
    el.querySelector("#ctrl-pick").addEventListener("click", () => $file.click());
    $file.addEventListener("change", () => {
      const f = $file.files && $file.files[0];
      if (f) {
        // 브라우저 보안상 전체 경로를 알 수 없으므로 파일명만 채우고 안내.
        $video.value = f.name;
        toast("전체 경로를 입력해 주세요 (브라우저 보안 제한)");
      }
    });

    $modes.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-mode]");
      if (!btn) return;
      mode = btn.dataset.mode;
      for (const c of $modes.querySelectorAll(".chip")) {
        c.setAttribute("aria-pressed", String(c === btn));
      }
    });

    $start.addEventListener("click", async () => {
      $start.disabled = true;
      try {
        await App.commands.start($video.value.trim(), mode);
      } finally {
        $start.disabled = false;
      }
    });
    $cancel.addEventListener("click", () => App.commands.cancel());

    App.on("job", (job) => {
      const running = job && job.state === "running";
      $cancel.disabled = !running;
      if (job && job.video) $video.value = job.video;
    });
    App.on("done", () => { $cancel.disabled = true; });
    App.on("error", () => { $cancel.disabled = true; });
  },
};
