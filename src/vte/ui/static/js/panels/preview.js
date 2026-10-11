/**
 * 미리보기 패널: 영상 재생 + 진행바 + 검출 박스 오버레이.
 * 상단 본문에 mount된다.
 *
 * 진행 이벤트(progress)를 받아 currentTime을 맞추고, detections 박스를
 * 오버레이 캔버스에 그린다. seek 이벤트를 받아 사용자 클릭 점프를 수행한다.
 */

export default {
  name: "preview",
  mountPoint: "preview",

  mount(el, App) {
    el.innerHTML = `
      <div class="video-stage">
        <video id="pv-video" muted playsinline></video>
        <canvas id="pv-canvas" class="overlay"></canvas>
        <div id="pv-placeholder" class="placeholder">
          <div class="glyph">▶</div>
          <div>추출을 시작하면 화면 진행이 표시됩니다</div>
        </div>
      </div>
      <div class="progress-wrap">
        <div class="progress-track"><div id="pv-fill" class="progress-fill"></div></div>
        <div class="progress-meta">
          <span id="pv-ts">0.0s</span>
          <span id="pv-frac">0%</span>
          <span id="pv-dur">–</span>
        </div>
      </div>
    `;

    const video = el.querySelector("#pv-video");
    const canvas = el.querySelector("#pv-canvas");
    const ctx = canvas.getContext("2d");
    const placeholder = el.querySelector("#pv-placeholder");
    const fill = el.querySelector("#pv-fill");
    const $ts = el.querySelector("#pv-ts");
    const $frac = el.querySelector("#pv-frac");
    const $dur = el.querySelector("#pv-dur");

    let videoSrc = null;

    function sizeCanvas() {
      const rect = canvas.parentElement.getBoundingClientRect();
      canvas.width = rect.width;
      canvas.height = rect.height;
    }
    window.addEventListener("resize", sizeCanvas);

    function drawBoxes(progress) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      if (!progress || !video.videoWidth) return;
      const sx = canvas.width / video.videoWidth;
      const sy = canvas.height / video.videoHeight;
      ctx.lineWidth = 2;
      ctx.font = "12px sans-serif";
      for (const pts of progress.detections || []) {
        if (!pts || pts.length < 2) continue;
        ctx.strokeStyle = "rgba(138,180,248,0.95)";
        ctx.beginPath();
        ctx.moveTo(pts[0][0] * sx, pts[0][1] * sy);
        for (let i = 1; i < pts.length; i++) ctx.lineTo(pts[i][0] * sx, pts[i][1] * sy);
        ctx.closePath();
        ctx.stroke();
      }
      ctx.fillStyle = "rgba(138,180,248,0.95)";
      for (const a of progress.active || []) {
        if (!a.rect) continue;
        const [x1, y1] = a.rect;
        ctx.fillText(a.text, x1 * sx, Math.max(12, y1 * sy - 4));
      }
    }

    function loadVideo(path) {
      if (path === videoSrc) return;
      videoSrc = path;
      video.src = `/api/media?path=${encodeURIComponent(path)}`;
      placeholder.style.display = "none";
      video.addEventListener("loadedmetadata", () => {
        sizeCanvas();
        $dur.textContent = `${video.duration.toFixed(1)}s`;
      }, { once: true });
    }

    App.on("job", (job) => {
      if (job && job.video) loadVideo(job.video);
    });

    App.on("progress", (p) => {
      if (!p) return;
      if (App.state && App.state.video) loadVideo(App.state.video);
      // 영상 위치를 진행 시각에 맞춘다 (사용자가 직접 스크럽 중이 아닐 때만)
      if (p.duration > 0 && !video.seeking) {
        const target = p.ts;
        if (Math.abs(video.currentTime - target) > 0.4) {
          video.currentTime = Math.min(target, video.duration || target);
        }
      }
      const pct = p.duration > 0 ? (p.ts / p.duration) * 100 : 0;
      fill.style.width = `${pct.toFixed(1)}%`;
      $ts.textContent = `${p.ts.toFixed(1)}s`;
      $frac.textContent = `${pct.toFixed(0)}%`;
      drawBoxes(p);
    });

    App.on("seek", (ts) => {
      if (video.src) {
        video.currentTime = ts;
        video.play().catch(() => {});
      }
    });

    App.on("reset", () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      fill.style.width = "0%";
      $ts.textContent = "0.0s";
      $frac.textContent = "0%";
    });

    App.on("done", () => { fill.style.width = "100%"; });
  },
};
