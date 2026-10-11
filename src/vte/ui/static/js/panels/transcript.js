/**
 * 추출 텍스트 패널: 하단에 실시간으로 확정된 텍스트를 쌓아 보여준다.
 *
 * - progress.closed: 진행 중 이미 확정된 구간 (실시간 갱신)
 * - done.events: 최종 병합·필터링된 결과
 * 타임코드를 클릭하면 미리보기 영상이 해당 시점으로 이동한다.
 */

function fmt(ts) {
  const m = Math.floor(ts / 60);
  const s = ts - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(2).padStart(5, "0")}`;
}

export default {
  name: "transcript",
  mountPoint: "transcript",

  mount(el, App) {
    el.innerHTML = `
      <div id="tt-live" class="transcript-list" style="margin-bottom:8px"></div>
      <div id="tt-final" class="transcript-list"></div>
      <div id="tt-empty" class="tt-empty">아직 추출된 텍스트가 없습니다</div>
    `;
    const $live = el.querySelector("#tt-live");
    const $final = el.querySelector("#tt-final");
    const $empty = el.querySelector("#tt-empty");
    const $count = document.getElementById("transcript-count");

    function row(item, { active = false, final = false } = {}) {
      const div = document.createElement("div");
      div.className = "tt-row" + (active ? " is-active" : "");
      div.dataset.id = item.id;
      const low = (item.confidence ?? 1) < 0.6;
      div.innerHTML = `
        <span class="tc" title="이 시점으로 이동">${fmt(item.start)}</span>
        <span class="txt"></span>
        <span class="conf${low ? " low" : ""}">${final ? (item.confidence ?? 1).toFixed(2) : "…"}</span>
      `;
      div.querySelector(".txt").textContent = item.text;
      div.querySelector(".tc").addEventListener("click", () => App.commands.seek(item.start));
      return div;
    }

    // 실시간: closed 구간을 id 기준으로 upsert
    App.on("progress", (p) => {
      if (!p) return;
      $empty.style.display = "none";
      const seen = new Set();
      for (const item of p.closed || []) {
        seen.add(String(item.id));
        let node = $live.querySelector(`[data-id="${item.id}"]`);
        if (!node) {
          node = row(item, { active: false });
          $live.appendChild(node);
        } else {
          node.querySelector(".txt").textContent = item.text;
        }
      }
      // 진행 중 활성 텍스트는 마지막에 강조 표시 (closed에 아직 안 들어간 것)
      for (const a of p.active || []) {
        if (seen.has(String(a.id))) continue;
        let node = $live.querySelector(`[data-id="live-${a.id}"]`);
        if (!node) {
          node = row({ id: `live-${a.id}`, start: a.start, text: a.text }, { active: true });
          $live.appendChild(node);
        } else {
          node.querySelector(".txt").textContent = a.text;
        }
      }
      $count.textContent = `${$live.children.length}개`;
    });

    // 완료: 최종 이벤트로 교체
    App.on("done", (events) => {
      $live.innerHTML = "";
      $final.innerHTML = "";
      const list = events || [];
      $empty.style.display = list.length ? "none" : "";
      for (const e of list) {
        $final.appendChild(row(e, { final: true }));
      }
      $count.textContent = `${list.length}개`;
    });

    App.on("reset", () => {
      $live.innerHTML = "";
      $final.innerHTML = "";
      $count.textContent = "0개";
      $empty.style.display = "";
    });

    App.on("error", () => {
      $empty.textContent = "추출 중 오류가 발생했습니다";
      $empty.style.display = "";
    });
  },
};
