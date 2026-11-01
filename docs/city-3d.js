import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";

const DATA = window.citySnapshot;
const stage = document.getElementById("stage");
const tooltip = document.getElementById("tooltip");
const panel = document.getElementById("sidepanel");
const botlist = document.getElementById("botlist");
const botdetail = document.getElementById("botdetail");
const ZONE = {};
DATA.districts.forEach((d) => {
  ZONE[d.id] = d;
});
const BOT = {};
DATA.bots.forEach((b) => {
  BOT[b.i] = b;
});

function esc(s) {
  return String(s).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
function cardHTML(b) {
  return (
    '<article class="prow" data-i="' +
    b.i +
    '">' +
    '<div class="bot-name">' +
    esc(b.name) +
    "</div>" +
    '<div class="badges"><span class="badge kind">' +
    esc(b.kind) +
    "</span>" +
    '<span class="badge hold-' +
    esc(b.hold) +
    '">' +
    esc(b.book) +
    "</span></div>" +
    '<p class="strat">' +
    esc(b.strat) +
    "</p>" +
    (b.watch ? '<div class="watch">' + esc(b.watch) + "</div>" : "") +
    b.perf +
    "</article>"
  );
}

let renderer;
try {
  renderer = new THREE.WebGLRenderer({
    antialias: true,
    powerPreference: "high-performance",
  });
} catch (e) {
  window.dispatchEvent(new CustomEvent("city-render-error"));
  throw e;
}
renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
renderer.domElement.setAttribute("aria-label", "Interactive 3D bot city");
renderer.setSize(stage.clientWidth, stage.clientHeight);
stage.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x04060d);
scene.fog = new THREE.FogExp2(0x05070f, 0.0013);

const camera = new THREE.PerspectiveCamera(
  46,
  stage.clientWidth / stage.clientHeight,
  0.5,
  3000,
);
camera.position.set(172, 150, 214);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 2, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.06;
controls.maxPolarAngle = 1.45;
controls.minDistance = 14;
controls.maxDistance = 640;
controls.autoRotate = !window.matchMedia("(prefers-reduced-motion: reduce)")
  .matches;
controls.autoRotateSpeed = 0.55;

/* --- textures --- */
function makeWindowTexture() {
  const c = document.createElement("canvas");
  c.width = 96;
  c.height = 192;
  const g = c.getContext("2d");
  g.fillStyle = "#070b1a";
  g.fillRect(0, 0, 96, 192);
  let seed = 987654321;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  for (let y = 0; y < 16; y++)
    for (let x = 0; x < 6; x++) {
      const r = rnd();
      if (r < 0.52)
        g.fillStyle =
          rnd() < 0.6 ? "rgba(255,214,140,0.95)" : "rgba(170,225,255,0.95)";
      else g.fillStyle = "rgba(15,23,46,1)";
      g.fillRect(6 + x * 15, 8 + y * 11.5, 9, 6.5);
    }
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}
function makeGlowTexture() {
  const c = document.createElement("canvas");
  c.width = c.height = 128;
  const g = c.getContext("2d");
  const gr = g.createRadialGradient(64, 64, 2, 64, 64, 64);
  gr.addColorStop(0, "rgba(255,255,255,0.85)");
  gr.addColorStop(0.4, "rgba(255,255,255,0.26)");
  gr.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = gr;
  g.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(c);
}
function makeLabelSprite(d) {
  const c = document.createElement("canvas");
  c.width = 640;
  c.height = 160;
  const g = c.getContext("2d");
  g.beginPath();
  if (g.roundRect) g.roundRect(12, 28, 616, 104, 26);
  else g.rect(12, 28, 616, 104);
  g.fillStyle = "rgba(4,8,20,0.78)";
  g.fill();
  g.lineWidth = 3;
  g.strokeStyle = d.color;
  g.stroke();
  g.textAlign = "center";
  let fs = 46;
  g.font = "700 " + fs + 'px "Avenir Next","Segoe UI",sans-serif';
  while (g.measureText(d.label).width > 580 && fs > 22) {
    fs -= 2;
    g.font = "700 " + fs + 'px "Avenir Next","Segoe UI",sans-serif';
  }
  g.fillStyle = "#eaf2ff";
  g.fillText(d.label, 320, 84);
  g.font = '600 29px "Avenir Next","Segoe UI",sans-serif';
  g.fillStyle = d.color;
  g.fillText(d.count + " BOTS", 320, 121);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  const sp = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: t, transparent: true, depthWrite: false }),
  );
  sp.scale.set(42, 10.5, 1);
  sp.position.set(d.cx, 58, d.cz);
  sp.userData.zone = d.id;
  return sp;
}

const winTex = makeWindowTexture();
const glowTex = makeGlowTexture();

/* --- ground, streets grid, stars --- */
const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(760, 760),
  new THREE.MeshBasicMaterial({ color: 0x04060d }),
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.05;
scene.add(ground);
const grid = new THREE.GridHelper(624, 78, 0x1e3a5f, 0x0c1730);
grid.position.y = 0.02;
grid.material.transparent = true;
grid.material.opacity = 0.5;
scene.add(grid);
(function addStars() {
  const pts = [];
  for (let i = 0; i < 700; i++) {
    const a = Math.random() * Math.PI * 2,
      e = Math.random() * Math.PI * 0.48 + 0.05,
      r = 640;
    pts.push(
      Math.cos(a) * Math.cos(e) * r,
      Math.sin(e) * r,
      Math.sin(a) * Math.cos(e) * r,
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  const stars = new THREE.Points(
    geo,
    new THREE.PointsMaterial({
      color: 0x8fb8ff,
      size: 1.7,
      sizeAttenuation: false,
      transparent: true,
      opacity: 0.75,
      fog: false,
    }),
  );
  scene.add(stars);
})();

/* --- districts: plots, borders, glow, labels, buildings --- */
const pickMeshes = []; // InstancedMesh per district (raycast: buildings)
const pickTargets = []; // buildings + plots + labels (raycast: clicks)
DATA.districts.forEach((d) => {
  const plot = new THREE.Mesh(
    new THREE.PlaneGeometry(d.pw + 6, d.pw + 6),
    new THREE.MeshBasicMaterial({
      color: d.color,
      transparent: true,
      opacity: 0.09,
      depthWrite: false,
    }),
  );
  plot.rotation.x = -Math.PI / 2;
  plot.position.set(d.cx, 0.05, d.cz);
  plot.userData.zone = d.id;
  scene.add(plot);
  pickTargets.push(plot);

  const h = d.pw / 2 + 3;
  const borderPts = [
    new THREE.Vector3(-h, 0, -h),
    new THREE.Vector3(h, 0, -h),
    new THREE.Vector3(h, 0, h),
    new THREE.Vector3(-h, 0, h),
  ];
  const border = new THREE.LineLoop(
    new THREE.BufferGeometry().setFromPoints(borderPts),
    new THREE.LineBasicMaterial({
      color: d.color,
      transparent: true,
      opacity: 0.85,
    }),
  );
  border.position.set(d.cx, 0.08, d.cz);
  scene.add(border);

  const glow = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: glowTex,
      color: d.color,
      transparent: true,
      opacity: 0.15,
      depthWrite: false,
    }),
  );
  glow.scale.set(d.pw * 1.7, d.pw * 1.7, 1);
  glow.position.set(d.cx, 3, d.cz);
  scene.add(glow);

  const label = makeLabelSprite(d);
  scene.add(label);
  pickTargets.push(label);

  const bots = DATA.bots.filter((b) => b.zone === d.id);
  const geo = new THREE.BoxGeometry(1, 1, 1);
  geo.translate(0, 0.5, 0);
  const im = new THREE.InstancedMesh(
    geo,
    new THREE.MeshBasicMaterial({ map: winTex }),
    bots.length,
  );
  const m4 = new THREE.Matrix4(),
    pv = new THREE.Vector3(),
    q = new THREE.Quaternion(),
    sc = new THREE.Vector3();
  const base = new THREE.Color(d.color);
  bots.forEach((b, j) => {
    pv.set(b.x, 0, b.z);
    sc.set(b.w, b.h, b.w);
    m4.compose(pv, q, sc);
    im.setMatrixAt(j, m4);
    b._base = base.clone().multiplyScalar(b.s);
    /* P/L tint: a bot with completed live trades shifts its building
       toward green (net profit) or red (net loss); no trades yet
       keeps the neutral district color. */
    if (b.pnl != null && b.calls > 0) {
      b._base.lerp(new THREE.Color(b.pnl >= 0 ? 0x2bff6a : 0xff3b30), 0.62);
    }
    im.setColorAt(j, b._base);
    b._mesh = im;
    b._inst = j;
  });
  im.instanceMatrix.needsUpdate = true;
  if (im.instanceColor) im.instanceColor.needsUpdate = true;
  im.userData.zone = d.id;
  im.userData.bots = bots;
  scene.add(im);
  pickMeshes.push(im);
  pickTargets.push(im);
});

/* --- camera flight + selection --- */
window.addEventListener("city-data", (e) => {
  for (const fresh of e.detail.bots) {
    const b = BOT[fresh.i];
    if (b && b.name === fresh.name) {
      Object.assign(b, {
        perf: fresh.perf,
        calls: fresh.calls,
        pnl: fresh.pnl,
      });
      b._base = new THREE.Color(ZONE[b.zone].color).multiplyScalar(b.s);
      if (b.pnl != null && b.calls > 0)
        b._base.lerp(new THREE.Color(b.pnl >= 0 ? 0x2bff6a : 0xff3b30), 0.62);
      setInstColor(b, b._base);
    }
  }
  if (selectedZone) selectZone(selectedZone);
});
let tween = null;
function flyTo(px, py, pz, tx, ty, tz, dur) {
  tween = {
    p0: camera.position.clone(),
    p1: new THREE.Vector3(px, py, pz),
    t0: controls.target.clone(),
    t1: new THREE.Vector3(tx, ty, tz),
    start: performance.now(),
    dur: dur || 1100,
  };
}
controls.addEventListener("start", () => {
  controls.autoRotate = false;
  tween = null;
});

let flash = null;
const tmpC = new THREE.Color(),
  whiteC = new THREE.Color(0xffffff);
function setInstColor(b, col) {
  b._mesh.setColorAt(b._inst, col);
  if (b._mesh.instanceColor) b._mesh.instanceColor.needsUpdate = true;
}
function flashBot(b) {
  if (flash) setInstColor(flash.bot, flash.bot._base);
  flash = { bot: b, until: performance.now() + 2600 };
}

let selectedZone = null;
function selectZone(zoneId, focusIdx) {
  selectedZone = zoneId;
  window.dispatchEvent(new CustomEvent("city-zone", { detail: zoneId }));
  if (window.__closeStats) window.__closeStats();
  const d = ZONE[zoneId];
  document.getElementById("sp-title").textContent = d.label;
  const sub = document.getElementById("sp-sub");
  sub.textContent = d.sub;
  sub.style.color = d.color;
  document.getElementById("sp-meta").textContent =
    d.count +
    " bots in this district · click a building or a row for the bot card";
  const bots = DATA.bots
    .filter((b) => b.zone === zoneId)
    .sort((a, b) => (a.name < b.name ? -1 : 1));
  botlist.innerHTML = bots.map(cardHTML).join("");
  botdetail.innerHTML = "";
  panel.classList.add("open");
  const len = Math.hypot(d.cx, d.cz) || 1;
  const ux = d.cx / len,
    uz = d.cz / len;
  flyTo(d.cx + ux * 92, 72, d.cz + uz * 92, d.cx, 4, d.cz, 1150);
  if (focusIdx != null) showBot(focusIdx, false);
}
function showBot(i, fly) {
  const b = BOT[i];
  if (!b) return;
  if (b.zone !== selectedZone) {
    selectZone(b.zone, i);
    return;
  }
  botdetail.innerHTML = cardHTML(b);
  window.dispatchEvent(new CustomEvent("city-bot", { detail: b.i }));
  botlist.querySelectorAll(".prow").forEach((r) => r.classList.remove("flash"));
  const row = botlist.querySelector('[data-i="' + i + '"]');
  if (row) {
    row.classList.add("flash");
    row.scrollIntoView({ block: "center" });
    setTimeout(() => row.classList.remove("flash"), 2600);
  }
  flashBot(b);
  if (fly !== false) flyTo(b.x + 30, 30, b.z + 30, b.x, b.h * 0.55, b.z, 1000);
}
botlist.addEventListener("click", (e) => {
  const row = e.target.closest(".prow");
  if (!row) return;
  showBot(+row.dataset.i);
});
botdetail.addEventListener("click", (e) => {
  const row = e.target.closest(".prow");
  if (!row) return;
  showBot(+row.dataset.i);
});
document
  .getElementById("spclose")
  .addEventListener("click", () => panel.classList.remove("open"));

/* --- picking: click a building, a plot, or a label; hover tooltip --- */
const ray = new THREE.Raycaster();
const ndc = new THREE.Vector2();
function setNDC(e) {
  const r = renderer.domElement.getBoundingClientRect();
  ndc.x = ((e.clientX - r.left) / r.width) * 2 - 1;
  ndc.y = -((e.clientY - r.top) / r.height) * 2 + 1;
}
let downX = 0,
  downY = 0;
renderer.domElement.addEventListener("pointerdown", (e) => {
  downX = e.clientX;
  downY = e.clientY;
});
renderer.domElement.addEventListener("pointerup", (e) => {
  if (Math.hypot(e.clientX - downX, e.clientY - downY) > 6) return;
  setNDC(e);
  ray.setFromCamera(ndc, camera);
  const hits = ray.intersectObjects(pickTargets, false);
  if (!hits.length) return;
  const h = hits[0];
  if (h.object.isInstancedMesh && h.instanceId !== undefined) {
    const b = h.object.userData.bots[h.instanceId];
    selectZone(b.zone);
    showBot(b.i);
  } else if (h.object.userData && h.object.userData.zone) {
    controls.autoRotate = false;
    selectZone(h.object.userData.zone);
  }
});
let hoverEvt = null;
renderer.domElement.addEventListener("pointermove", (e) => {
  hoverEvt = e;
  const r = stage.getBoundingClientRect();
  tooltip.style.left = e.clientX - r.left + 14 + "px";
  tooltip.style.top = e.clientY - r.top + 12 + "px";
});
renderer.domElement.addEventListener("pointerleave", () => {
  hoverEvt = null;
  tooltip.style.display = "none";
});

function fitRenderer() {
  const w = stage.clientWidth,
    hgt = stage.clientHeight;
  if (!w || !hgt) return;
  camera.aspect = w / hgt;
  camera.updateProjectionMatrix();
  renderer.setSize(w, hgt);
}
window.addEventListener("resize", fitRenderer);
document.addEventListener("fullscreenchange", () =>
  setTimeout(fitRenderer, 60),
);

/* --- main loop --- */
function animate() {
  requestAnimationFrame(animate);
  if (document.hidden || !document.body.classList.contains("view-3d")) return;
  const now = performance.now();
  if (tween) {
    let k = (now - tween.start) / tween.dur;
    if (k > 1) k = 1;
    const e = 1 - Math.pow(1 - k, 3);
    camera.position.lerpVectors(tween.p0, tween.p1, e);
    controls.target.lerpVectors(tween.t0, tween.t1, e);
    if (k === 1) tween = null;
  }
  if (flash) {
    if (now > flash.until) {
      setInstColor(flash.bot, flash.bot._base);
      flash = null;
    } else {
      const p = 0.5 + 0.5 * Math.sin(now / 160);
      tmpC.setHex(0xfacc15).lerp(whiteC, p * 0.45);
      setInstColor(flash.bot, tmpC);
    }
  }
  if (hoverEvt) {
    setNDC(hoverEvt);
    ray.setFromCamera(ndc, camera);
    const hits = ray.intersectObjects(pickMeshes, false);
    if (hits.length && hits[0].instanceId !== undefined) {
      const b = hits[0].object.userData.bots[hits[0].instanceId];
      tooltip.innerHTML =
        esc(b.name) + '<span class="tz">' + esc(ZONE[b.zone].label) + "</span>";
      tooltip.style.display = "block";
      renderer.domElement.style.cursor = "pointer";
    } else {
      tooltip.style.display = "none";
      renderer.domElement.style.cursor = "";
    }
    hoverEvt = null;
  }
  controls.update();
  renderer.render(scene, camera);
}
animate();
window.__cityReady = true;
window.__flyToBot = function (i) {
  const b = BOT[i];
  if (!b) return;
  controls.autoRotate = false;
  selectZone(b.zone);
  showBot(i);
};
window.__selectDistrict = function (z) {
  if (!ZONE[z]) return;
  controls.autoRotate = false;
  selectZone(z);
};

window.__cityHome = () => {
  panel.classList.remove("open");
  flyTo(172, 150, 214, 0, 2, 0, 900);
};
window.__cityPause = (value) => {
  controls.autoRotate = !value;
};
window.dispatchEvent(new CustomEvent("city-render-ready"));
