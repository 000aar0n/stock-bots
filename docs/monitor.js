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
  const empty = $("selection").innerHTML;
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
    const focus = data.districts.find((d) => d.id === zone);
    const viewport = focus
      ? `${focus.cx - 43} ${focus.cz - 52} 86 96`
      : "-170 -184 350 360";
    const districts = data.districts
      .filter((d) => !zone || d.id === zone)
      .map((d) => {
        const bots = data.bots.filter((b) => b.zone === d.id);
        return (
          '<g class="map-district' +
          (zone === d.id ? " selected" : "") +
          '" data-zone="' +
          d.id +
          '" role="button" tabindex="0" aria-label="' +
          esc(d.label) +
          ", " +
          d.count +
          ' bots"><rect class="district-ground" x="' +
          (d.cx - 36) +
          '" y="' +
          (d.cz - 36) +
          '" width="72" height="72" rx="3" fill="#14212a" stroke="#30454f"/><text x="' +
          (d.cx - 34) +
          '" y="' +
          (d.cz - 41) +
          '">' +
          esc(d.id.toUpperCase()) +
          " / " +
          d.count +
          "</text>" +
          bots
            .map(
              (b) =>
                '<rect aria-hidden="true" class="map-building' +
                (selected === b.i ? " selected" : "") +
                '" data-bot="' +
                b.i +
                '" x="' +
                (b.x - b.w / 2) +
                '" y="' +
                (b.z - b.w / 2) +
                '" width="' +
                b.w +
                '" height="' +
                b.w +
                '" rx=".5" fill="' +
                (b.pnl === null
                  ? d.color
                  : b.pnl >= 0
                    ? "#9be5cd"
                    : "#ef8f95") +
                '" opacity="' +
                (zone && zone !== d.id
                  ? 0.25
                  : 0.5 + Math.min(b.h / 80, 0.45)) +
                '"><title>' +
                esc(b.name) +
                " · " +
                (b.pnl === null
                  ? "No completed shadow trades"
                  : money(b.pnl) + " closed shadow P/L") +
                "</title></rect>",
            )
            .join("") +
          "</g>"
        );
      });
    $("citymap").innerHTML =
      '<svg viewBox="' +
      viewport +
      '" role="group" aria-label="Bot city districts"><defs><pattern id="street-grid" width="13" height="13" patternUnits="userSpaceOnUse"><path d="M13 0H0V13" fill="none" stroke="#182832" stroke-width=".4"/></pattern></defs><rect x="-175" y="-185" width="360" height="370" fill="url(#street-grid)"/>' +
      districts.join("") +
      '<text x="0" y="146" fill="#506c78" font-family="monospace" font-size="8">BOT CITY / ' +
      data.summary.bots +
      ' STRATEGIES</text><path d="M80 160H155m0 0-4-3m4 3-4 3" stroke="#506c78" fill="none"/></svg>';
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
      $("selection").innerHTML = empty;
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
      '<div><span class="bot-kind">' +
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
    inspect();
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
        if (
          innerWidth > 700 &&
          !matchMedia("(prefers-reduced-motion: reduce)").matches
        )
          void setView(true);
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
      : "2D / INTERACTIVE";
    $("view-note").textContent = three
      ? "Drag to orbit · Scroll to zoom · Select a building."
      : "Select a district or a building to inspect its bots.";
    $("sidepanel").hidden = !three;
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
        threePromise = import("./city-3d.js");
      }
      await Promise.race([
        threePromise,
        new Promise((_, reject) =>
          setTimeout(() => reject(Error("3D timeout")), 9000),
        ),
      ]);
      if (want3d && selected !== null) window.__flyToBot?.(selected);
    } catch (e) {
      threeFailed = true;
      applyView(false);
      $("view-note").textContent =
        "3D unavailable on this device. Every bot is accessible in the city map.";
    } finally {
      $("city-loading").hidden = true;
    }
  }
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
    if (b) selectBot(+b.dataset.bot);
    else if (z) selectZone(z.dataset.zone);
  });
  $("citymap").addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " ") {
      const z = e.target.closest("[data-zone]");
      if (z) {
        e.preventDefault();
        selectZone(z.dataset.zone);
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
  $("fullscreen").addEventListener("click", async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await $("stage").parentElement.requestFullscreen();
    } catch {
      $("view-note").textContent = "Fullscreen is unavailable in this browser.";
    }
  });
  document.addEventListener("fullscreenchange", () => {
    $("fullscreen").setAttribute(
      "aria-label",
      document.fullscreenElement ? "Exit fullscreen" : "Enter fullscreen",
    );
  });
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
      $("search").focus();
      $("directory").scrollIntoView({ block: "start" });
    }
    if (e.key === "Escape") {
      $("sidepanel").classList.remove("open");
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
