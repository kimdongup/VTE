/**
 * 패널 레지스트리 + 이벤트 버스.
 *
 * 패널 계약: `{ name: string, mount(root: { el, sidebar }), }`
 * - mount 인자 el: 전용 DOM 컨테이너 (preview/transcript는 본문, 나머지는 사이드바)
 * - App.emit/on 으로 전역 이벤트 수신·발행
 * - App.state 를 읽어 현재 상태 참조, App.commands 로 명령 실행
 */

const listeners = new Map();

export const App = {
  panels: [],
  state: null,
  commands: {},

  register(panel) {
    if (!panel || !panel.name || typeof panel.mount !== "function") {
      throw new Error("panel must have { name, mount }");
    }
    this.panels.push(panel);
  },

  /** 전역 이벤트 수신 등록. */
  on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, new Set());
    listeners.get(type).add(fn);
    return () => listeners.get(type).delete(fn);
  },

  /** 전역 이벤트 발행. */
  emit(type, payload) {
    const set = listeners.get(type);
    if (!set) return;
    for (const fn of set) {
      try {
        fn(payload);
      } catch (err) {
        console.error(`[panel:${type}]`, err);
      }
    }
  },

  /** 패널들을 DOM에 mount한다. boot 시 1회 호출. */
  boot() {
    const previewBody = document.getElementById("preview-body");
    const transcriptBody = document.getElementById("transcript-body");
    const sidebar = document.querySelector("[data-panel='sidebar']");
    for (const panel of this.panels) {
      let container;
      if (panel.mountPoint === "preview") {
        container = previewBody;
      } else if (panel.mountPoint === "transcript") {
        container = transcriptBody;
      } else {
        container = sidebar;
      }
      const el = document.createElement("div");
      el.className = `panel-mount panel-mount--${panel.name}`;
      container.appendChild(el);
      try {
        panel.mount(el, this);
      } catch (err) {
        console.error(`[panel:${panel.name}] mount failed`, err);
      }
    }
  },
};

/** 짧은 토스트 알림. */
export function toast(message, ms = 2600) {
  const el = document.getElementById("toast");
  if (!el) return;
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.remove("show"), ms);
}
