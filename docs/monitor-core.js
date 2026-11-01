(function (root) {
  "use strict";
  const validTime = (value) =>
    typeof value === "string" &&
    Number.isFinite(Date.parse(value)) &&
    /[Zz]|[+-]\d\d:\d\d$/.test(value);
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const text = (value, max = 500) =>
    typeof value === "string" ? value.slice(0, max) : "";
  function validate(raw, now = Date.now()) {
    if (
      raw?.schemaVersion !== 1 ||
      !validTime(raw.generatedAt) ||
      Date.parse(raw.generatedAt) > now + 60000 ||
      !Array.isArray(raw.bots) ||
      !raw.bots.length ||
      raw.bots.length > 10000 ||
      !Array.isArray(raw.districts)
    )
      throw Error("Invalid monitor snapshot");
    const districts = raw.districts.map((d) => {
      if (
        !/^[a-z]+$/.test(d.id) ||
        !/^#[0-9a-f]{6}$/i.test(d.color) ||
        !["cx", "cz", "pw"].every((k) => finite(d[k])) ||
        d.pw <= 0
      )
        throw Error("Invalid district");
      return {
        id: d.id,
        label: text(d.label, 80),
        sub: text(d.sub, 120),
        color: d.color,
        cx: d.cx,
        cz: d.cz,
        pw: d.pw,
      };
    });
    const zones = new Set(districts.map((d) => d.id)),
      ids = new Set(),
      names = new Set();
    if (zones.size !== districts.length) throw Error("Duplicate district");
    const bots = raw.bots.map((b) => {
      if (
        !Number.isInteger(b.i) ||
        b.i < 0 ||
        ids.has(b.i) ||
        !b.name ||
        names.has(b.name) ||
        !zones.has(b.zone) ||
        !["x", "z", "w", "h", "s"].every((k) => finite(b[k])) ||
        b.w <= 0 ||
        b.h <= 0 ||
        !Number.isInteger(b.calls) ||
        b.calls < 0 ||
        (b.pnl !== null && !finite(b.pnl))
      )
        throw Error("Invalid bot record");
      ids.add(b.i);
      names.add(b.name);
      return {
        i: b.i,
        name: text(b.name, 100),
        kind: text(b.kind, 40),
        hold: text(b.hold, 40),
        book: text(b.book, 50),
        strat: text(b.strat, 1500),
        watch: text(b.watch, 400),
        tickers: Array.isArray(b.tickers)
          ? b.tickers.map((t) => text(t, 20)).slice(0, 300)
          : [],
        zone: b.zone,
        calls: b.calls,
        pnl: b.calls ? b.pnl : null,
        sessions: Number.isInteger(b.sessions) ? Math.max(0, b.sessions) : 0,
        eligible: b.eligible === true,
        state: b.state === "benched" ? "benched" : "registered",
        ranked: b.ranked === true,
        arenaCalls: Number.isInteger(b.arenaCalls) ? b.arenaCalls : 0,
        arenaPnl: finite(b.arenaPnl) ? b.arenaPnl : null,
        x: b.x,
        z: b.z,
        w: b.w,
        h: b.h,
        s: b.s,
      };
    });
    for (const d of districts)
      d.count = bots.filter((b) => b.zone === d.id).length;
    const ranked = bots.filter((b) => b.calls && b.pnl !== null);
    const runtime = {
      at:
        validTime(raw.runtime?.at) && Date.parse(raw.runtime.at) <= now + 60000
          ? raw.runtime.at
          : null,
      status: [
        "READY",
        "MARKET_CLOSED",
        "NEEDS_DATA",
        "CLOSING_INTRADAY_PAPER",
      ].includes(raw.runtime?.status)
        ? raw.runtime.status
        : "UNCONNECTED",
    };
    const judge =
      raw.judge &&
      Number.isInteger(raw.judge.scored) &&
      raw.judge.scored >= 0 &&
      Number.isInteger(raw.judge.unscored) &&
      Number.isInteger(raw.judge.sessions) &&
      (raw.judge.net === null || finite(raw.judge.net))
        ? {
            scored: raw.judge.scored,
            unscored: raw.judge.unscored,
            sessions: raw.judge.sessions,
            net: raw.judge.scored ? raw.judge.net : null,
          }
        : null;
    return {
      schemaVersion: 1,
      generatedAt: raw.generatedAt,
      lastCallAt: validTime(raw.lastCallAt) ? raw.lastCallAt : null,
      runtime,
      judge,
      warnings: Array.isArray(raw.warnings)
        ? raw.warnings.map((w) => text(w, 200)).slice(0, 5)
        : [],
      basis: text(raw.basis, 800),
      evidence: { trades: 20, sessions: 5 },
      summary: {
        bots: bots.length,
        symbols: new Set(bots.flatMap((b) => b.tickers)).size,
        ranked: ranked.length,
        completed: bots.reduce((s, b) => s + b.calls, 0),
        rankable: bots.filter((b) => b.ranked).length,
        eligible: bots.filter(
          (b) => b.ranked && b.calls >= 20 && b.sessions >= 5,
        ).length,
        pnl: ranked.length ? ranked.reduce((s, b) => s + b.pnl, 0) : null,
      },
      districts,
      bots,
    };
  }
  function freshness(data, now = Date.now()) {
    if (!data.runtime.at)
      return {
        label: "Published registry · runner unconnected",
        fresh: false,
        detail:
          "No verified runner heartbeat. Publication does not establish runtime activity.",
      };
    const age = now - Date.parse(data.runtime.at);
    if (age > 300000)
      return {
        label: "Runner heartbeat is old",
        fresh: false,
        detail:
          "Last runner heartbeat " +
          data.runtime.at +
          ". Published stats may be out of date.",
      };
    const states = {
      READY: "Runner reporting · shadow mode",
      MARKET_CLOSED: "Runner reporting · market closed",
      NEEDS_DATA: "Runner needs verified data",
      CLOSING_INTRADAY_PAPER: "Runner closing intraday paper positions",
    };
    return {
      label: states[data.runtime.status] || "Runner state unknown",
      fresh: data.runtime.status !== "NEEDS_DATA",
      detail: "Last verified heartbeat " + data.runtime.at + ".",
    };
  }
  function filterBots(
    data,
    { query = "", zone = "", role = "", book = "", sort = "name" } = {},
  ) {
    const words = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
    return data.bots
      .filter(
        (b) =>
          (!zone || b.zone === zone) &&
          (!role || b.kind === role) &&
          (!book || b.hold === book) &&
          words.every((w) =>
            (b.name + " " + b.watch + " " + b.strat).toLowerCase().includes(w),
          ),
      )
      .sort((a, b) =>
        sort === "pnl"
          ? (b.pnl ?? -Infinity) - (a.pnl ?? -Infinity) ||
            a.name.localeCompare(b.name)
          : sort === "calls"
            ? b.calls - a.calls || a.name.localeCompare(b.name)
            : a.name.localeCompare(b.name),
      );
  }
  const api = { validate, freshness, filterBots };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.CityCore = api;
})(typeof window !== "undefined" ? window : globalThis);
