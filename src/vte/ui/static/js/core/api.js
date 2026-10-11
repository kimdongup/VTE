/**
 * REST + SSE 클라이언트.
 * 모든 패널이 이 모듈을 통해 서버와 통신한다.
 */

async function request(method, url, body) {
  const opts = { method, headers: {} };
  if (body !== undefined) {
    opts.headers["Content-Type"] = "application/json";
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(url, opts);
  const isJson = (res.headers.get("Content-Type") || "").includes("json");
  const data = isJson ? await res.json() : await res.text();
  if (!res.ok) {
    const message = (data && data.error) || `${res.status} ${res.statusText}`;
    throw new Error(message);
  }
  return data;
}

export const api = {
  /** 추출 잡 시작. 성공 시 { job } 반환, 실패(409 등) 시 throw. */
  startExtract(payload) {
    return request("POST", "/api/extract", payload);
  },
  cancel() {
    return request("POST", "/api/cancel", {});
  },
  status() {
    return request("GET", "/api/status");
  },
  /**
   * SSE 구독. 핸들러는 이벤트 타입(snapshot/progress/done/error/ping)과
   * 페이로드를 받는다. 반환값은 연결 종료 함수.
   */
  subscribe(handlers) {
    const es = new EventSource("/api/events");
    es.onmessage = (ev) => {
      let msg;
      try {
        msg = JSON.parse(ev.data);
      } catch {
        return;
      }
      const fn = handlers[msg.type];
      if (fn) fn(msg);
    };
    es.onerror = () => {
      // EventSource는 자동 재연결한다. 사용자가 알 필요는 없음.
    };
    return () => es.close();
  },
  /** 내보내기 텍스트를 받아 다운로드로 저장. */
  async downloadExport(fmt) {
    const res = await fetch(`/api/export?format=${encodeURIComponent(fmt)}`);
    if (!res.ok) {
      let message = `${res.status}`;
      try {
        message = (await res.json()).error || message;
      } catch { /* non-json */ }
      throw new Error(message);
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vte_output.${fmt}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
