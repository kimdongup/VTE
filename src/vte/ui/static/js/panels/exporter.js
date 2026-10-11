/**
 * 내보내기 패널: 완료된 결과를 SRT/TXT/JSON/ASS로 다운로드.
 * 사이드바 하단에 mount된다.
 */

import { api } from "../core/api.js";
import { toast } from "../core/registry.js";

const FORMATS = ["srt", "txt", "json", "ass"];

export default {
  name: "exporter",
  mountPoint: "sidebar",

  mount(el, App) {
    el.innerHTML = `
      <div class="side-card">
        <h3>내보내기</h3>
        <div class="export-row">
          ${FORMATS.map((f) => `<button class="btn btn--sm" data-fmt="${f}" type="button" disabled>.${f}</button>`).join("")}
        </div>
        <div id="ex-note" class="export-note">추출이 완료되면 활성화됩니다</div>
      </div>
    `;
    const $note = el.querySelector("#ex-note");
    const buttons = [...el.querySelectorAll("[data-fmt]")];

    function setEnabled(enabled) {
      for (const b of buttons) b.disabled = !enabled;
      $note.textContent = enabled ? "원하는 형식을 선택해 다운로드하세요" : "추출이 완료되면 활성화됩니다";
    }

    for (const b of buttons) {
      b.addEventListener("click", async () => {
        try {
          await api.downloadExport(b.dataset.fmt);
          toast(`.${b.dataset.fmt} 파일을 저장했습니다`);
        } catch (err) {
          toast(err.message);
        }
      });
    }

    App.on("done", (events) => setEnabled((events || []).length > 0));
    App.on("reset", () => setEnabled(false));
    App.on("error", () => setEnabled(false));
  },
};

