"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );
  const money = (value) =>
    value === null
      ? "—"
      : new Intl.NumberFormat("en-US", {
          style: "currency",
          currency: "USD",
          maximumFractionDigits: 2,
        }).format(value);
  const time = (value) =>
    value
      ? new Date(value).toLocaleString("en-US", {
          timeZone: "America/New_York",
          month: "short",
          day: "numeric",
          hour: "numeric",
          minute: "2-digit",
          timeZoneName: "short",
        })
      : "Unavailable";
  let fingerprint = "",
    data = null,
    zone = "",
    selected = null,
    limit = 40,
    busy = false,
    threePromise = null,
    threeFailed = false,
    want3d = false;
  function color(b) {
    return b.pnl === null ? "" : b.pnl >= 0 ? "positive" : "negative";
  }
  function sourceStatus() {
    if (!data) return;
    const status = CityCore.freshness(data);
    $("feed-status").textContent = status.label;
    $("feed-dot").classList.toggle("fresh", status.fresh);
    $("snapshot-time").textContent = "Snapshot " + time(data.generatedAt);
    $("runtime-label").textContent = data.runtime.at
      ? data.runtime.status.replaceAll("_", " ") + " · " + time(data.runtime.at)
      : "No verified runner heartbeat.";
    $("data-notes").textContent =
      "Published data checked every minute. Last paper event: " +
      time(data.lastCallAt) +
      ". " +
      status.detail;
  }
  function showError(message) {
    $("feed-error").hidden = !message;
    $("feed-error").textContent = message;
  }
  function summary() {
    $("all-count").textContent = $("total-bots").textContent =
      data.summary.bots;
    $("total-symbols").textContent = data.summary.symbols;
    $("total-ranked").textContent = data.summary.ranked;
    $("total-pnl").textContent = money(data.summary.pnl);
    $("total-pnl").className =
      data.summary.pnl === null
        ? ""
        : data.summary.pnl >= 0
          ? "positive"
          : "negative";
    $("completed-label").textContent = data.summary.completed
      ? data.summary.completed + " completed shadow round trips"
      : "No completed shadow trades in the published source";
    $("eligible-count").textContent =
      data.summary.eligible + " / " + data.summary.rankable;
    $("basis").textContent = data.basis;
    $("district-count").textContent = data.districts.length;
    const currentRole = $("role").value;
    $("role").innerHTML =
      '<option value="">All roles</option>' +
      [...new Set(data.bots.map((b) => b.kind))]
        .sort()
        .map((k) => '<option value="' + esc(k) + '">' + esc(k) + "</option>")
        .join("");
    $("role").value = currentRole;
    $("districts").innerHTML = data.districts
      .map(
        (d) =>
          '<button class="district' +
          (zone === d.id ? " active" : "") +
          '" data-zone="' +
          d.id +
          '" aria-pressed="' +
          (zone === d.id) +
          '"><i style="background:' +
          d.color +
          '"></i><span>' +
          esc(d.label) +
          "</span><b>" +
          d.count +
          "</b></button>",
      )
      .join("");
  }
  function map() {
    if (data) {
      $("citymap").innerHTML = CityMap.render(data, zone, selected);
      $("citymap").classList.toggle("focused", Boolean(zone));
      if (!zone && innerWidth <= 700) $("citymap").scrollLeft = ($("citymap").scrollWidth - $("citymap").clientWidth) / 2;
    }
  }
  function sectorPanel() {
    if (!data || selected !== null) return;
    const d = data.districts.find((d) => d.id === zone);
    const rows = CityCore.filterBots(data, { zone, query: $("city-search").value });
    $("selection").innerHTML = '<h2>' + esc(d?.label || 'All city bots') + '</h2><p>' +
      esc(d?.sub || 'Every bot in your registry, grouped into city sectors.') + '</p><p class="sector-count">' + rows.length + ' bots</p><div class="sector-bots">' + rows.map(b =>
      '<button class="sector-bot" data-bot="' + b.i + '"><span>' + esc(b.name) + '</span><small>' + esc(b.kind) + ' · ' + esc(b.book) + '</small></button>').join('') + (rows.length ? '' : '<p>No bots match. Try a name or ticker.</p>') + '</div>';
  }
  function directory() {
    if (!data) return;
    const rows = CityCore.filterBots(data, {
      query: $("search").value,
      zone,
      role: $("role").value,
      book: $("book").value,
      sort: $("sort").value,
    });
    $("result-count").textContent =
      rows.length + " of " + data.bots.length + " bots";
    $("empty-results").hidden = rows.length > 0;
    $("show-more").hidden = rows.length <= limit;
    $("bot-rows").innerHTML = rows
      .slice(0, limit)
      .map((b) => {
        const d = data.districts.find((d) => d.id === b.zone),
          eligible = b.ranked && b.calls >= 20 && b.sessions >= 5;
        return (
          '<tr><td><button data-bot="' +
          b.i +
          '">' +
          esc(b.name) +
          "</button><small>" +
          esc(b.strat.slice(0, 135)) +
          (b.strat.length > 135 ? "…" : "") +
          "</small></td><td>" +
          esc(d.label) +
          "</td><td>" +
          esc(b.book) +
          "</td><td>" +
          b.calls +
          '</td><td class="' +
          color(b) +
          '">' +
          money(b.pnl) +
          '</td><td><span class="evidence' +
          (eligible ? " ready" : "") +
          '">' +
          (!b.ranked ? "UNRANKED" : eligible ? "THRESHOLD MET" : "UNPROVEN") +
          "</span></td></tr>"
        );
      })
      .join("");
  }
  function inspect() {
    if (selected === null) {
      sectorPanel();
      return;
    }
    const b = data.bots.find((b) => b.i === selected);
    if (!b) {
      selected = null;
      inspect();
      return;
    }
    const d = data.districts.find((d) => d.id === b.zone);
    $("selection").innerHTML =
      '<button class="back-sector" data-back-sector>← All bots in this sector</button><div><span class="bot-kind">' +
      esc(b.kind.toUpperCase()) +
      '</span><span class="bot-kind">' +
      esc(b.book) +
      "</span><h2>" +
      esc(b.name) +
      "</h2><p>" +
      esc(b.strat) +
      '</p></div><div class="selected-metrics"><div>District <b>' +
      esc(d.label) +
      "</b></div><div>Registry state <b>" +
      esc(b.state) +
      '</b></div><div>Closed shadow P/L <b class="' +
      color(b) +
      '">' +
      money(b.pnl) +
      "</b></div><div>Completed trades <b>" +
      b.calls +
      "</b></div><div>Trading sessions <b>" +
      b.sessions +
      "</b></div><div>Evidence <b>" +
      (!b.ranked
        ? "Unranked role"
        : b.calls >= 20 && b.sessions >= 5
          ? "Threshold met"
          : "Unproven") +
      "</b></div>" +
      (b.arenaCalls
        ? "<div>ARENA / backtest <b>" +
          b.arenaCalls +
          " trades · " +
          money(b.arenaPnl) +
          "</b></div>"
        : "") +
      "</div>" +
      (b.name === "JUDGE"
        ? '<div class="selected-metrics"><div>JUDGE decisions <b>' +
          (data.judge
            ? data.judge.scored +
              " scored / " +
              data.judge.unscored +
              " unscored"
            : "Unavailable") +
          "</b></div><div>Counterfactual net <b>" +
          money(data.judge?.net ?? null) +
          '</b></div><p class="subtle">Same-session-close paper outcomes. Separate from realized trades.</p></div>'
        : "") +
      '<div><span class="section-eyebrow">WATCHLIST</span><p class="ticker-list">' +
      (b.tickers.length
        ? b.tickers.map((t) => "<span>" + esc(t) + "</span>").join("")
        : "Citywide role") +
      '</p><p class="subtle">Paper reference sizing. No HTMW executions are implied by these results.</p></div>';
  }
  function selectZone(id, fromScene = false) {
    zone = id;
    selected = null;
    $("city-search").value = "";
    document.body.classList.toggle("panel-open", Boolean(id));
    document.body.classList.remove("sectors-open");
    $("toggle-sectors").setAttribute("aria-expanded", "false");
    sectorPanel();
    limit = 40;
    $("city-title").textContent =
      data.districts.find((d) => d.id === id)?.label || "All districts";
    $("all-districts").classList.toggle("active", !id);
    $("all-districts").setAttribute("aria-pressed", String(!id));
    summary();
    map();
    directory();
    if (!fromScene && want3d && window.__selectDistrict && id)
      window.__selectDistrict(id);
  }
  function selectBot(id, fromScene = false) {
    selected = id;
    const active = data.bots.find(b => b.i === id);
    if (active && zone !== active.zone) {
      zone = active.zone;
      $("city-title").textContent = data.districts.find(d => d.id === zone).label;
      summary();
      directory();
    }
    document.body.classList.add("panel-open");
    inspect();
    $("inspector").scrollTop = 0;
    map();
    const b = data.bots.find((b) => b.i === id);
    if (!fromScene && want3d && window.__flyToBot) window.__flyToBot(id);
    if (b) history.replaceState(null, "", "#bot=" + encodeURIComponent(b.name));
  }
  async function refresh() {
    if (busy) return;
    busy = true;
    $("refresh").disabled = true;
    try {
      const r = await fetch("data.json?check=" + Date.now(), {
        cache: "no-store",
        signal: AbortSignal.timeout(12000),
      });
      if (!r.ok) throw Error("Snapshot request failed");
      const next = CityCore.validate(await r.json());
      if (data && Date.parse(next.generatedAt) < Date.parse(data.generatedAt))
        throw Error("Older publication received");
      const serialized = JSON.stringify(next),
        changed = serialized !== fingerprint;
      fingerprint = serialized;
      data = next;
      // HTML for the retained 3D module is built locally from validated numbers,
      // never accepted from a published JSON field.
      for (const b of data.bots)
        b.perf =
          '<div class="perf">' +
          b.calls +
          " completed shadow trades · " +
          esc(money(b.pnl)) +
          "</div>";
      window.citySnapshot = data;
      if (changed) {
        summary();
        map();
        directory();
        inspect();
        window.dispatchEvent(new CustomEvent("city-data", { detail: data }));
      }
      sourceStatus();
      showError(data.warnings.join(" "));
      $("checked-time").textContent =
        "Last successful check " + time(new Date().toISOString());
      if (!window.__cityInitialized) {
        window.__cityInitialized = true;
        const name = decodeURIComponent(
          location.hash.startsWith("#bot=") ? location.hash.slice(5) : "",
        );
        const b = data.bots.find((b) => b.name === name);
        if (b) selectBot(b.i);
        // The complete isometric city works immediately, including phones and
        // devices without WebGL. Orbit 3D is an explicit enhancement.
        applyView(false);
      }
    } catch (e) {
      showError(
        data
          ? "Could not refresh published data. Keeping the last validated snapshot; source timestamps have not changed."
          : "Published data could not be loaded. Use Refresh to retry.",
      );
      $("feed-status").textContent = data
        ? "Refresh failed · showing saved snapshot"
        : "Snapshot unavailable";
      $("feed-dot").classList.remove("fresh");
    } finally {
      busy = false;
      $("refresh").disabled = false;
    }
  }
  function applyView(three) {
    want3d = three;
    document.body.classList.toggle("view-3d", three);
    $("view-3d").setAttribute("aria-pressed", String(three));
    $("view-map").setAttribute("aria-pressed", String(!three));
    $("view-state").textContent = three
      ? "3D / ORBIT & ZOOM"
      : "ISOMETRIC / ALL BOTS";
    $("view-note").textContent = three
      ? "Drag to orbit · Scroll to zoom · Select a building."
      : innerWidth <= 700 ? "Swipe to explore · Tap a sector · Home to return" : "Select a sector · Select a building for its bot · Home to return";
    $("sidepanel").hidden = true;
  }
  async function setView(three) {
    if (!three) {
      applyView(false);
      return;
    }
    if (!data) return;
    if (threeFailed) {
      $("view-note").textContent =
        "3D is unavailable here. The complete city map remains interactive.";
      return;
    }
    applyView(true);
    $("city-loading").hidden = false;
    try {
      if (!threePromise) {
        const probe = document.createElement("canvas"),
          gl = probe.getContext("webgl2") || probe.getContext("webgl");
        if (!gl) throw Error("WebGL unavailable");
        gl.getExtension("WEBGL_lose_context")?.loseContext();
        threePromise = import("./city-3d.js?v=city3-bafa4ea");
      }
      await Promise.race([
        threePromise,
        new Promise((_, reject) =>
          setTimeout(() => reject(Error("3D timeout")), 9000),
        ),
      ]);
      if (want3d && selected !== null) window.__flyToBot?.(selected);
      else if (want3d && zone) window.__selectDistrict?.(zone);
    } catch (e) {
      threeFailed = true;
      applyView(false);
      $("view-note").textContent =
        "3D unavailable on this device. Every bot is accessible in the city map.";
    } finally {
      $("city-loading").hidden = true;
    }
  }
  $("toggle-sectors").addEventListener("click", () => {
    const open = document.body.classList.toggle("sectors-open");
    $("toggle-sectors").setAttribute("aria-expanded", String(open));
    if (open) document.body.classList.remove("panel-open");
  });
  function showData() {
    const open = document.body.classList.toggle("show-data");
    $("toggle-data").setAttribute("aria-expanded", String(open));
    if (open) $("directory").scrollIntoView({ block: "start" });
    else window.scrollTo({ top: 0 });
  }
  $("toggle-data").addEventListener("click", showData);
  $("open-directory").addEventListener("click", (e) => {
    e.preventDefault();
    document.body.classList.add("panel-open");
    if (data) { selected = null; sectorPanel(); }
    $("city-search").focus();
  });
  $("city-search").addEventListener("input", () => { selected = null; sectorPanel(); });
  $("selection").addEventListener("click", (e) => {
    if (e.target.closest("[data-back-sector]")) {
      selected = null;
      $("city-search").value = "";
      sectorPanel();
      map();
      history.replaceState(null, "", location.pathname);
      return;
    }
    const b = e.target.closest("[data-bot]");
    if (b) selectBot(+b.dataset.bot);
  });
  $("refresh").addEventListener("click", refresh);
  $("districts").addEventListener("click", (e) => {
    const b = e.target.closest("[data-zone]");
    if (b) selectZone(b.dataset.zone);
  });
  $("all-districts").addEventListener("click", () => {
    selectZone("");
    window.__cityHome?.();
  });
  $("citymap").addEventListener("click", (e) => {
    const b = e.target.closest("[data-bot]"),
      z = e.target.closest("[data-zone]");
    if (z && zone !== z.dataset.zone) selectZone(z.dataset.zone);
    else if (b) selectBot(+b.dataset.bot);
    else if (z) selectZone(z.dataset.zone);
  });
  $("citymap").addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      const z = e.target.closest("[data-zone]");
      const b = e.target.closest("[data-bot]");
      if (b || z) {
        e.preventDefault();
        if (b) selectBot(+b.dataset.bot);
        else selectZone(z.dataset.zone);
      }
    }
  });
  $("bot-rows").addEventListener("click", (e) => {
    const b = e.target.closest("[data-bot]");
    if (b) {
      selectBot(+b.dataset.bot);
      $("inspector").scrollIntoView({ block: "nearest", behavior: "instant" });
    }
  });
  for (const id of ["search", "role", "book", "sort"])
    $(id).addEventListener(id === "search" ? "input" : "change", () => {
      limit = 40;
      directory();
    });
  $("clear-filters").addEventListener("click", () => {
    $("search").value = $("role").value = $("book").value = "";
    $("sort").value = "name";
    selectZone("");
  });
  $("show-more").addEventListener("click", () => {
    limit += 40;
    directory();
  });
  $("clear-selection").addEventListener("click", () => {
    selected = null;
    document.body.classList.remove("panel-open");
    inspect();
    map();
    history.replaceState(null, "", location.pathname);
  });
  $("view-map").addEventListener("click", () => setView(false));
  $("view-3d").addEventListener("click", () => setView(true));
  $("reset-view").addEventListener("click", () => {
    selected = null;
    selectZone("");
    inspect();
    window.__cityHome?.();
  });
  function fullscreenLabel() {
    $("fullscreen").setAttribute("aria-label", document.fullscreenElement || document.body.classList.contains("city-expanded") ? "Exit fullscreen" : "Enter fullscreen");
  }
  $("fullscreen").addEventListener("click", async () => {
    if (document.fullscreenElement) await document.exitFullscreen();
    else if (document.body.classList.contains("city-expanded")) document.body.classList.remove("city-expanded");
    else {
      try { await document.querySelector(".observatory").requestFullscreen(); }
      catch { document.body.classList.add("city-expanded"); }
    }
    fullscreenLabel();
    window.dispatchEvent(new Event("resize"));
  });
  document.addEventListener("fullscreenchange", fullscreenLabel);
  window.addEventListener("city-zone", (e) => {
    if (zone !== e.detail) selectZone(e.detail, true);
  });
  window.addEventListener("city-bot", (e) => {
    if (selected !== e.detail) selectBot(e.detail, true);
  });
  document.addEventListener("keydown", (e) => {
    if (
      e.key === "/" &&
      !["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName)
    ) {
      e.preventDefault();
      document.body.classList.add("panel-open");
      $("city-search").focus();
    }
    if (e.key === "Escape") {
      $("sidepanel").classList.remove("open");
      document.body.classList.remove("panel-open", "sectors-open", "city-expanded");
      fullscreenLabel();
      $("toggle-sectors").setAttribute("aria-expanded", "false");
    }
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) void refresh();
  });
  setInterval(() => {
    if (!document.hidden) void refresh();
  }, 60000);
  setInterval(() => {
    if (data && !busy) sourceStatus();
  }, 30000);
  void refresh();
})();
